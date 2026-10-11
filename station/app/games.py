"""Real-time multiplayer trivia over WebSockets."""
import asyncio
import random
from dataclasses import dataclass, field

QUESTIONS = [
    {"q": "Which plant is known for turning to follow the sun?", "options": ["Sunflower", "Cactus", "Fern", "Moss"], "answer": 0},
    {"q": "What gas do plants absorb from the air?", "options": ["Oxygen", "Carbon dioxide", "Helium", "Neon"], "answer": 1},
    {"q": "How many legs does an insect have?", "options": ["4", "6", "8", "10"], "answer": 1},
    {"q": "Which season do many trees drop their leaves?", "options": ["Spring", "Summer", "Autumn", "None"], "answer": 2},
    {"q": "Bees mainly collect what from flowers?", "options": ["Nectar", "Sand", "Seeds", "Water only"], "answer": 0},
]


@dataclass
class Player:
    user_id: str
    nickname: str
    ws: object
    score: int = 0
    answered: bool = False


@dataclass
class Room:
    name: str
    players: dict = field(default_factory=dict)
    state: str = "lobby"  # lobby | running | finished
    index: int = -1
    questions: list = field(default_factory=list)
    timer: asyncio.Task | None = None
    event: asyncio.Event | None = None


class TriviaManager:
    def __init__(self, seconds: int = 15, on_event=lambda e: None):
        self.rooms: dict[str, Room] = {}
        self.seconds, self.on_event = seconds, on_event

    def room(self, name: str) -> Room:
        return self.rooms.setdefault(name, Room(name))

    async def broadcast(self, room: Room, msg: dict):
        for p in list(room.players.values()):
            try:
                await p.ws.send_json(msg)
            except Exception:
                room.players.pop(p.user_id, None)

    def scores(self, room: Room):
        return sorted(({"nickname": p.nickname, "score": p.score} for p in room.players.values()),
                      key=lambda x: -x["score"])

    async def join(self, room: Room, user, ws):
        room.players[user["id"]] = Player(user["id"], user["nickname"], ws)
        await self.broadcast(room, {"type": "players", "state": room.state, "scores": self.scores(room)})

    async def leave(self, room: Room, user_id: str):
        room.players.pop(user_id, None)
        if not room.players:
            if room.timer:
                room.timer.cancel()
            self.rooms.pop(room.name, None)
        else:
            await self.broadcast(room, {"type": "players", "state": room.state, "scores": self.scores(room)})

    async def handle(self, room: Room, user, msg: dict):
        kind = msg.get("type")
        if kind == "start" and room.state != "running":
            await self.start(room)
        elif kind == "answer" and room.state == "running":
            p = room.players.get(user["id"])
            choice = msg.get("choice")
            if p and not p.answered and isinstance(choice, int) and not isinstance(choice, bool):
                p.answered = True
                if choice == room.questions[room.index]["answer"]:
                    p.score += 10
                if all(x.answered for x in room.players.values()) and room.event:
                    room.event.set()

    async def start(self, room: Room):
        if room.timer:
            room.timer.cancel()
        room.state, room.index = "running", -1
        room.questions = random.sample(QUESTIONS, len(QUESTIONS))
        for p in room.players.values():
            p.score = 0
        self.on_event("game_running")
        room.timer = asyncio.create_task(self._run(room))

    async def _run(self, room: Room):
        try:
            for i, q in enumerate(room.questions):
                room.index = i
                room.event = asyncio.Event()
                for p in room.players.values():
                    p.answered = False
                await self.broadcast(room, {"type": "question", "number": i + 1, "total": len(room.questions),
                                            "q": q["q"], "options": q["options"], "seconds": self.seconds})
                try:
                    await asyncio.wait_for(room.event.wait(), self.seconds)
                except asyncio.TimeoutError:
                    pass
                await self.broadcast(room, {"type": "result", "answer": q["answer"], "scores": self.scores(room)})
                await asyncio.sleep(0.05 if self.seconds <= 1 else 2)
            room.state = "finished"
            self.on_event("game_finished")
            await self.broadcast(room, {"type": "finished", "scores": self.scores(room)})
        except asyncio.CancelledError:
            pass
