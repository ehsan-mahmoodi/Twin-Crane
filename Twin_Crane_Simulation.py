import salabim as sim
import random
import pygame

sim.yieldless(False)

# =========================================================
# USER SETTINGS
# =========================================================
N_TRACKS = 16

SIM_MINUTES = 10
RUN_UNTIL_CLOSED = False
SIM_DURATION = sim.inf if RUN_UNTIL_CLOSED else SIM_MINUTES * 60

SIM_SPEED = 5
JOB_INTERVAL = (4, 9)

T_SPEED = 0.9
H_SPEED = 0.6
SERVICE_TIME = 0.25
DISPATCH_PERIOD = 0.4
MAX_PENDING_AGE = 90

WAIT_STEP = 0.25
IDLE_POLL = 0.3

# =========================================================
# WINDOW / LAYOUT (Pygame Coordinates)
# =========================================================
WIN_W = 1450         
WIN_H = 900           
PANEL_W = 380         
MARGIN_L = PANEL_W + 18

TRACK_PX = (WIN_W - MARGIN_L - 24) // N_TRACKS

RAIL_Y = 650          
TROL_H = 22
HOIST_MAX = 220

RAIL_X0 = MARGIN_L - 15
RAIL_X1 = MARGIN_L + N_TRACKS * TRACK_PX + 15
TROL_BOT = RAIL_Y - TROL_H
GROUND_Y = TROL_BOT - HOIST_MAX - 18

TITLE_FS = 18
SECTION_FS = 16
BODY_FS = 14
SMALL_FS = 12
TRACK_FS = 14

# =========================================================
# COLORS
# =========================================================
C_BG = (18, 18, 32)
C_SKY = (22, 32, 55)
C_GROUND = (38, 50, 38)
C_COLUMN = (48, 62, 78)
C_COL_LINE = (72, 92, 112)
C_RAIL = (50, 68, 86)
C_RAIL_LINE = (92, 132, 162)
C_TICK = (192, 192, 88)
C_TICK_LBL = (200, 210, 200)

C_ROPE_S = (152, 192, 222)
C_ROPE_L = (222, 162, 152)

C_PANEL_BG = (10, 12, 28)
C_PANEL_EDGE = (36, 66, 106)
C_SEP_S = (26, 50, 86)
C_SEP_L = (76, 26, 26)
C_TXT_S = (182, 215, 245)
C_TXT_L = (245, 195, 182)
C_TXT_T = (170, 225, 170)

C_LOG_BG = (6, 8, 20)
C_LOG_EDGE = (20, 46, 76)
C_LOG_HDR = (100, 210, 120)
C_LOG_TXT = (120, 205, 135)
C_LEG_TXT = (220, 228, 236)

C_EMPTY_S = (62, 92, 132)
C_EMPTY_L = (132, 62, 62)

# =========================================================
# SHARED DATA
# =========================================================
MAX_LOG = 12
event_log = []
pending_calls = []
move_reservations = {}

# =========================================================
# EVENT & FILE LOGGING
# =========================================================
DEBUG_LOG_FILE = "twin_crane_debug_log.txt"
debug_seq = 0

def write_debug(line):
    with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def debug(msg):
    global debug_seq
    debug_seq += 1
    t = env.now() if "env" in globals() else 0.0
    write_debug(f"{debug_seq:06d} | t={t:8.3f} | {msg}")

def log(msg):
    event_log.append(msg)
    if len(event_log) > MAX_LOG:
        event_log.pop(0)
    debug(f"EVENT | {msg}")

def snapshot(tag="SNAPSHOT"):
    if "stiff_crane" in globals() and "ladle_crane" in globals():
        msg = (
            f"{tag} | "
            f"STIFF(track={stiff_crane.track}, phase={stiff_crane.cphase}, "
            f"load={stiff_crane.nparts}, job1={stiff_crane.job1}) | "
            f"LADLE(track={ladle_crane.track}, phase={ladle_crane.cphase}, "
            f"load={ladle_crane.nparts}, job1={ladle_crane.job1}) | "
            f"pending={len(pending_calls)}"
        )
        debug(msg)

with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
    f.write("Strict Spatial JIT Debug Log\n")
    f.write("============================\n")

def track_center(track):
    return MARGIN_L + track * TRACK_PX + TRACK_PX / 2

# =========================================================
# HELPERS (Strict Spatial Logic)
# =========================================================
def current_other(crane):
    return ladle_crane if crane.is_stiff else stiff_crane

def is_idle_unloaded(crane):
    return crane.job1 is None and crane.nparts == 0

def reservation_owner(track):
    return move_reservations.get(track)

def release_reservations(crane):
    dead = [k for k, v in move_reservations.items() if v == crane.crane_name]
    for k in dead: del move_reservations[k]

def can_reserve_track(crane, track):
    if not (0 <= track < N_TRACKS): return False
    other = current_other(crane)
    # Cannot reserve if other crane is physically there
    if other.track == track: return False
    # Cannot reserve if other crane has already reserved it
    owner = reservation_owner(track)
    if owner is not None and owner != crane.crane_name: return False
    return True

def reserve_track(crane, track):
    if can_reserve_track(crane, track):
        move_reservations[track] = crane.crane_name
        return True
    return False

def request_blocker_escape(blocker, requester):
    """
    Calculates the requester's full upcoming path and assigns a 
    relocate target to the idle blocker so it clears the entire area.
    """
    if not is_idle_unloaded(blocker):
        return False

    req_pts = [requester.track]
    if requester.job1: 
        req_pts.extend(requester.job1)

    if blocker.is_stiff:
        ladle_min = min(req_pts)
        target = max(0, ladle_min - 1)
    else:
        stiff_max = max(req_pts)
        target = min(N_TRACKS - 1, stiff_max + 1)

    if blocker.track == target or blocker.relocate_to == target:
        return False

    blocker.relocate_to = target
    blocker.relocate_reason = f"yield to {requester.crane_name}"
    log(f"[yield] {blocker.crane_name} -> T{target}")
    return True

# =========================================================
# CRANE COMPONENT
# =========================================================
class Crane(sim.Component):
    def setup(self, label, start_track, color, is_stiff):
        self.label = label
        self.crane_name = "STIFF_CRANE" if is_stiff else "LADLE_CRANE"
        self.is_stiff = is_stiff
        self.color = color

        self.track = start_track
        self.hoist_y = 0.0
        self.nparts = 0
        self.x_val = [None]
        self.job1 = None

        self.relocate_to = None
        self.relocate_reason = ""

        self.cphase = "idle"
        self.cinfo = "Waiting for job"
        self.jobs_done = 0

    def process(self):
        while True:
            if self.job1 is None:
                if self.relocate_to is not None and self.track != self.relocate_to:
                    self.cphase = "relocate"
                    self.cinfo = f"Yield -> T{self.relocate_to}"
                    yield from self._travel(self.relocate_to, relocating=True)
                    if self.track == self.relocate_to:
                        log(f"[yield] {self.crane_name} parked @ T{self.relocate_to}")
                    self.relocate_to = None
                    self.relocate_reason = ""
                    self.cphase = "idle"
                    self.cinfo = "Waiting for job"
                    continue

                self.cphase = "idle"
                self.cinfo = "Waiting for job"
                yield self.hold(IDLE_POLL)
                continue

            pickup, dropoff = self.job1
            self.x_val[0] = pickup

            self.cphase = "move_to_pickup"
            self.cinfo = f"-> Pickup T{pickup}"
            yield from self._travel(pickup)

            self.cphase = "lower_hook"
            self.cinfo = "v Lowering hook"
            yield from self._hoist("down")

            self.nparts = 1
            self.cphase = "attach"
            self.cinfo = "* Load hooked"
            log(f"[{self.crane_name}] Hooked @ T{pickup}")
            yield self.hold(SERVICE_TIME)

            self.cphase = "raise_load"
            self.cinfo = "^ Raising load"
            yield from self._hoist("up")

            self.x_val[0] = dropoff

            self.cphase = "move_to_dropoff"
            self.cinfo = f"-> Dropoff T{dropoff}"
            yield from self._travel(dropoff)

            self.cphase = "lower_load"
            self.cinfo = "v Lowering load"
            yield from self._hoist("down")

            self.nparts = 0
            self.cphase = "detach"
            self.cinfo = "o Released"
            log(f"[{self.crane_name}] Released @ T{dropoff}")
            yield self.hold(SERVICE_TIME)

            self.cphase = "raise_empty"
            self.cinfo = "^ Raise empty"
            yield from self._hoist("up")

            self.jobs_done += 1
            log(f"[{self.crane_name}] Done #{self.jobs_done}")

            self.job1 = None
            self.x_val[0] = None
            self.cphase = "idle"
            self.cinfo = f"Idle (done {self.jobs_done})"
            snapshot(f"{self.crane_name}_POST_JOB")

    def _travel(self, target, relocating=False):
        """
        Strict step-by-step movement ensuring NO physical crossing
        and NO moving into unreserved/occupied tracks.
        """
        while self.track != target:
            other = current_other(self)
            d = 1 if target > self.track else -1
            nxt = self.track + d

            if not (0 <= nxt < N_TRACKS): 
                break

            # If moving towards the other crane, ensure it is escaping if idle
            if (self.is_stiff and nxt >= other.track) or (not self.is_stiff and nxt <= other.track):
                if is_idle_unloaded(other): 
                    request_blocker_escape(other, self)
                self.cinfo = f"[wait] {'LADLE' if self.is_stiff else 'STIFF'} blocks T{nxt}"
                yield self.hold(WAIT_STEP)
                continue

            # Check physical occupation and logical reservations
            occ_block = (other.track == nxt)
            res_owner = reservation_owner(nxt)
            res_block = res_owner not in (None, self.crane_name)

            if occ_block or res_block:
                if occ_block and is_idle_unloaded(other): 
                    request_blocker_escape(other, self)
                self.cinfo = f"[wait] T{nxt} occupied"
                yield self.hold(WAIT_STEP)
                continue

            # Lock the track before moving
            if not reserve_track(self, nxt):
                self.cinfo = f"[wait] reserve T{nxt}"
                yield self.hold(WAIT_STEP)
                continue

            yield self.hold(T_SPEED)
            self.track = nxt
            release_reservations(self)

        release_reservations(self)

    def _hoist(self, direction):
        steps = 12
        delta = (1.0 / steps) if direction == "down" else (-1.0 / steps)
        for _ in range(steps):
            self.hoist_y = max(0.0, min(1.0, self.hoist_y + delta))
            yield self.hold(H_SPEED / steps)

    def px(self): return track_center(self.track)
    def hook_py(self): return TROL_BOT - self.hoist_y * HOIST_MAX

# =========================================================
# DISPATCHER & LOGIC (JIT Dispaching + Strict Spatial Rules)
# =========================================================
def crane_can_accept(crane): 
    # JIT: Only accept if totally idle and not currently relocating
    return crane.job1 is None and crane.relocate_to is None

def path_feasible(crane, pickup, dropoff):
    """
    Mathematical guarantee that jobs assigned will NEVER cause a spatial overlap.
    """
    other = current_other(crane)
    
    # If the other crane is entirely idle, we can assign anything as long as we leave 
    # it 1 track of space to retreat to at the far edge.
    if is_idle_unloaded(other):
        if crane.is_stiff: 
            return pickup <= (N_TRACKS - 2) and dropoff <= (N_TRACKS - 2)
        else: 
            return pickup >= 1 and dropoff >= 1
            
    # If the other crane is active, find out EVERY track it will touch for its job
    other_pts = [other.track]
    if other.job1: 
        other_pts.extend(other.job1)
    if other.relocate_to is not None: 
        other_pts.append(other.relocate_to)
        
    # Strictly forbid overlapping zones
    if crane.is_stiff:
        ladle_min = min(other_pts)
        return pickup < ladle_min and dropoff < ladle_min
    else:
        stiff_max = max(other_pts)
        return pickup > stiff_max and dropoff > stiff_max

def pdf_metric(crane, pickup_track):
    slot = 0 if crane.nparts == 0 else 1
    ref = crane.x_val[slot] if crane.x_val[slot] is not None else crane.track
    return abs(ref - pickup_track)

def assign_to_crane(crane, pickup, dropoff):
    if crane.job1 is None:
        crane.job1 = (pickup, dropoff)
        crane.x_val[0] = pickup
        log(f"Job-> {crane.crane_name} P:T{pickup} D:T{dropoff}")
        return True
    return False

class Dispatcher(sim.Component):
    def process(self):
        while True:
            if pending_calls:
                remaining = []
                for call in pending_calls:
                    pu, do, born = call["pickup"], call["dropoff"], call["born"]
                    
                    # Fetch candidates that meet strict spatial rules
                    candidates = [(pdf_metric(c, pu), 0 if c.is_stiff else 1, c) for c in (stiff_crane, ladle_crane) if crane_can_accept(c) and path_feasible(c, pu, do)]
                    
                    if candidates:
                        # Assign to the closest valid crane
                        assign_to_crane(sorted(candidates, key=lambda x: (x[0], x[1]))[0][2], pu, do)
                    else:
                        if env.now() - born > MAX_PENDING_AGE: 
                            log(f"[!] Rejected P:T{pu} D:T{do}")
                        else: 
                            remaining.append(call)
                pending_calls[:] = remaining
                
                if len(pending_calls) > 0:
                    snapshot("DISPATCH_DEFERRED")
            yield self.hold(DISPATCH_PERIOD)

def enqueue_call(pu, do):
    pending_calls.append({"pickup": pu, "dropoff": do, "born": env.now()})
    log(f"Call  P:T{pu} D:T{do}")

class JobGen(sim.Component):
    def process(self):
        for pu, do in [(1, 4), (9, 7), (3, 2), (8, 10)]: enqueue_call(pu, do)
        while True:
            yield self.hold(random.uniform(*JOB_INTERVAL))
            pu, do = random.randint(0, N_TRACKS - 1), random.randint(0, N_TRACKS - 1)
            while do == pu: do = random.randint(0, N_TRACKS - 1)
            enqueue_call(pu, do)

# =========================================================
# SALABIM ENVIRONMENT (Headless)
# =========================================================
env = sim.Environment(trace=False)
env.animation_parameters(animate=False)

stiff_crane = Crane(label="S", start_track=1, color=(30, 144, 255), is_stiff=True) 
ladle_crane = Crane(label="L", start_track=N_TRACKS - 2, color=(255, 99, 71), is_stiff=False) 
dispatcher = Dispatcher()
job_gen = JobGen()

# =========================================================
# PYGAME VISUALIZATION ENGINE 
# =========================================================
pygame.init()
screen = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption("Twin Crane Simulation — Strict Spatial Pygame")
clock = pygame.time.Clock()

font_title = pygame.font.SysFont("Segoe UI", TITLE_FS, bold=True)
font_section = pygame.font.SysFont("Segoe UI", SECTION_FS, bold=True)
font_body = pygame.font.SysFont("Consolas", BODY_FS)
font_small = pygame.font.SysFont("Consolas", SMALL_FS)
font_track = pygame.font.SysFont("Segoe UI", TRACK_FS, bold=True)

def py_y(y): return WIN_H - y

def draw_rect(color, x0, y0, x1, y1, width=0):
    w, h = abs(x1 - x0), abs(y1 - y0)
    pygame.draw.rect(screen, color, (x0, py_y(max(y0, y1)), w, h), width)

def draw_text(text, x, y, font, color):
    lines = str(text).split('\n')
    current_y = py_y(y) - font.get_linesize()
    for line in lines:
        surf = font.render(line, True, color)
        screen.blit(surf, (x, current_y))
        current_y += font.get_linesize() + 2

def short_status(s, n=40):
    s = str(s)
    return s if len(s) <= n else s[:n - 3] + "..."

def crane_status_text(crane):
    load_txt = "CARRYING" if crane.nparts else "empty"
    return (
        f"Track : T{crane.track}\n"
        f"Phase : {short_status(crane.cphase, 20)}\n"
        f"Status: {short_status(crane.cinfo, 40)}\n"
        f"Load  : {load_txt}   Done: {crane.jobs_done}\n"
        f"Job   : {crane.job1}\n"
        f"Reloc : {crane.relocate_to}"
    )

running = True
snapshot("SIM_START")

while running and env.now() < SIM_DURATION:
    dt = clock.tick(60) / 1000.0  
    env.run(till=env.now() + (dt * SIM_SPEED))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill(C_BG)

    draw_rect(C_SKY, RAIL_X0, RAIL_Y + 8, RAIL_X1, WIN_H - 2)
    draw_rect(C_GROUND, RAIL_X0, GROUND_Y, RAIL_X1, GROUND_Y + 14)

    for cx in [RAIL_X0 + 9, RAIL_X1 - 9]:
        draw_rect(C_COLUMN, cx - 7, GROUND_Y + 14, cx + 7, RAIL_Y + 8)
        draw_rect(C_COL_LINE, cx - 7, GROUND_Y + 14, cx + 7, RAIL_Y + 8, 1)

    draw_rect(C_RAIL, RAIL_X0, RAIL_Y - 6, RAIL_X1, RAIL_Y + 8)
    draw_rect(C_RAIL_LINE, RAIL_X0, RAIL_Y - 6, RAIL_X1, RAIL_Y + 8, 1)

    for i in range(N_TRACKS):
        tx = MARGIN_L + i * TRACK_PX + TRACK_PX / 2
        draw_rect(C_TICK, tx - 2, RAIL_Y - 5, tx + 2, RAIL_Y + 5)
        draw_text(f"T{i}", tx - 8, RAIL_Y + 20, font_track, C_TICK_LBL)

    for c, is_s in [(stiff_crane, True), (ladle_crane, False)]:
        cx, cy = c.px(), c.hook_py()
        hook_color = (255, 215, 0) if c.nparts else (C_EMPTY_S if is_s else C_EMPTY_L)
        rope_color = C_ROPE_S if is_s else C_ROPE_L
        
        pygame.draw.line(screen, rope_color, (cx, py_y(TROL_BOT)), (cx, py_y(cy - 14)), 2)
        draw_rect(c.color, cx - 20, TROL_BOT, cx + 20, RAIL_Y - 6)
        draw_rect((255, 255, 255), cx - 20, TROL_BOT, cx + 20, RAIL_Y - 6, 1)
        draw_text("S" if is_s else "L", cx - 5, RAIL_Y - 14, font_body, (255, 255, 255))
        draw_rect(hook_color, cx - 12, cy - 14, cx + 12, cy)
        draw_rect((255, 255, 255), cx - 12, cy - 14, cx + 12, cy, 1)

    PX, PW = 5, PANEL_W - 8
    draw_rect(C_PANEL_BG, PX, 4, PX + PW, WIN_H - 4)
    draw_rect(C_PANEL_EDGE, PX, 4, PX + PW, WIN_H - 4, 1)
    
    draw_text("TWIN CRANE SYSTEM", PX + 10, WIN_H - 10, font_title, (30, 144, 255))

    STIFF_TOP = WIN_H - 40
    BLOCK_H = 140
    LADLE_TOP = STIFF_TOP - BLOCK_H - 15
    INFO_TOP = LADLE_TOP - BLOCK_H - 15
    INFO_H = 90
    LOG_TOP = INFO_TOP - INFO_H - 15
    LOG_H = 300
    LEG_TOP = LOG_TOP - LOG_H - 15

    def p_x(): return PX + 10

    draw_rect((9, 14, 32), PX, STIFF_TOP - BLOCK_H, PX + PW, STIFF_TOP)
    draw_rect(C_SEP_S, PX, STIFF_TOP - BLOCK_H, PX + PW, STIFF_TOP, 1)
    draw_text("[S] STIFF CRANE", p_x(), STIFF_TOP - 10, font_section, (30, 144, 255))
    draw_text(crane_status_text(stiff_crane), p_x(), STIFF_TOP - 30, font_body, C_TXT_S)

    draw_rect((26, 10, 18), PX, LADLE_TOP - BLOCK_H, PX + PW, LADLE_TOP)
    draw_rect(C_SEP_L, PX, LADLE_TOP - BLOCK_H, PX + PW, LADLE_TOP, 1)
    draw_text("[L] LADLE CRANE", p_x(), LADLE_TOP - 10, font_section, (255, 99, 71))
    draw_text(crane_status_text(ladle_crane), p_x(), LADLE_TOP - 30, font_body, C_TXT_L)

    draw_rect(C_LOG_BG, PX, INFO_TOP - INFO_H, PX + PW, INFO_TOP)
    draw_rect(C_LOG_EDGE, PX, INFO_TOP - INFO_H, PX + PW, INFO_TOP, 1)
    info_str = (
        f"Time   : {env.now():.1f} s\n"
        f"Rule   : Strict spatial reservations\n"
        f"Pending: {len(pending_calls)}"
    )
    draw_text(info_str, p_x(), INFO_TOP - 10, font_body, C_TXT_T)

    draw_rect(C_LOG_BG, PX, LOG_TOP - LOG_H, PX + PW, LOG_TOP)
    draw_rect(C_LOG_EDGE, PX, LOG_TOP - LOG_H, PX + PW, LOG_TOP, 1)
    draw_text("EVENT LOG", p_x(), LOG_TOP - 10, font_section, C_LOG_HDR)
    
    log_y = LOG_TOP - 35
    for msg in reversed(event_log):
        draw_text(msg, p_x(), log_y, font_small, C_LOG_TXT)
        log_y -= 18

    draw_rect(C_LOG_BG, PX, LEG_TOP - 80, PX + PW, LEG_TOP)
    draw_rect(C_LOG_EDGE, PX, LEG_TOP - 80, PX + PW, LEG_TOP, 1)
    draw_text("LEGEND", p_x(), LEG_TOP - 10, font_section, C_LEG_TXT)
    
    legends = [((30, 144, 255), "[S] Stiff crane"), ((255, 99, 71), "[L] Ladle crane"), ((255, 215, 0), "Load carried")]
    for i, (col, lbl) in enumerate(legends):
        ly = LEG_TOP - 35 - i * 18
        draw_rect(col, PX + 10, ly, PX + 20, ly + 10)
        draw_text(lbl, PX + 28, ly + 10, font_small, C_LEG_TXT)

    pygame.display.flip()

snapshot("SIM_END")
pygame.quit()