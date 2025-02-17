import sys
import json
from europi import *
from math import sin, pi, floor
from time import sleep, sleep_ms, ticks_ms, sleep_us
import _thread, gc

LONG_PRESS_DURATION = 500
MIN_FREQ = 0.01
MAX_FREQ = 2
DISP_W = 128
DISP_H = 32
CV_RATE = 48000
MAX_MORPH_SINE = 1.0
MAX_MORPH_LOGISTIC = 4.0
INTERP_STEP = 0.1
TGT_TOL = 0.175
CACHE_MAX = 10
SLEEP_MS = 10

SQ1 = (0, 0, 4, 4)
SQ2 = (6, 0, 4, 4)

def load_saved_state(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("equation_dict", []), data.get("byte_array_dict", {}), data.get("global_settings", {}))
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        sys.exit(1)
        
    # -----------------------------------------------------------------------
    # eq engine state 3
    # -----------------------------------------------------------------------

class EquationEngine:
    def __init__(self, w, h):
        self.width = w
        self.height = h
        self.theta_lookup = [(x / w) * 2 * pi for x in range(w)]
        self.cache = {}

    def clear_cache_if_needed(self):
        if len(self.cache) >= CACHE_MAX:
            self.cache.clear()

    def fold(self, s, th=1.0):
        i = 0
        while (s > th or s < -th) and i < 10:
            if s > th: s = th - (s - th)
            else: s = -th - (s + th)
            i += 1
        return s

    def compute_waveform(self, eq_data, morph, freq):
        key = (eq_data["id"], round(morph, 3))
        if key in self.cache:
            return self.cache[key]
        self.clear_cache_if_needed()
        wf = []
        if eq_data["title"] == "Logistic":
            x_val = 0.5
            for i in range(self.width):
                try:
                    x_val = morph * x_val * (1.0 - x_val)
                except:
                    x_val = 0.0
                x_val = 0.0 if x_val < 0.0 else (1.0 if x_val > 1.0 else x_val)
                y = int(x_val * (self.height - 1))
                wf.append((i, y))
        else:
            for i, theta in enumerate(self.theta_lookup):
                if eq_data["title"] == "SineOsc":
                    s = self.fold(sin(theta) * morph, 1.0)
                elif eq_data["title"] == "SawOsc":
                    t = theta / (2*pi)
                    s = 2 * (t*freq - floor(0.5 + t*freq))
                    s *= morph
                elif eq_data["title"] == "SquareOsc":
                    s = 1.0 if sin(theta) >= 0 else -1.0
                    s *= morph
                else:
                    s = 0.0
                y = int(((s*0.5) + 0.5) * (self.height - 1))
                wf.append((i, y))
        self.cache[key] = tuple(wf)
        return self.cache[key]

    def interp_waveform(self, w1, w2, f):
        return tuple((x, int(y1*(1-f) + y2*f)) for (x,y1),(x2,y2) in zip(w1,w2))
    
    # -----------------------------------------------------------------------
    # little squares for din ain & wave morhping
    # -----------------------------------------------------------------------

class DisplayController:
    def __init__(self, w, h):
        self.width = w
        self.height = h
        self.last_wave = None
        self.interp = 1.0

    def render_waveform(self, waveform, interp_active=False):
        oled.fill(0)
        for x, y in waveform:
            if 0 <= x < self.width and 0 <= y < self.height:
                oled.pixel(x, y, 1)
        oled.fill_rect(*SQ1, 1)
        if interp_active:
            oled.fill_rect(*SQ2, 1)
        oled.show()
        self.last_wave = waveform
        
    # -----------------------------------------------------------------------
    # codex state 1 & 2
    # -----------------------------------------------------------------------

class Codex:
    def __init__(self):
        eq_list, byte_map, global_set = load_saved_state("saved_state_Codex.txt")
        self.equations, self.byte_arrays, self.global_settings = eq_list, byte_map, global_set
        self.screen = self.global_settings.get("last_screen", 1)
        self.equation_index = self.global_settings.get("last_equation", 0) % len(self.equations)
        self.controls = ["AIN", "k1", "k2"]
        self.assignments = {c: None for c in self.controls}
        self.ctrl_index = 0
        self.var_index = 0
        self.buttons = {
            'b1': {
                'pin': b1,
                'press_time': None,
                'long_press_triggered': False,
                'short_press_handler': self.on_b1_short_press,
                'long_press_handler': self.on_b1_long_press
            },
            'b2': {
                'pin': b2,
                'press_time': None,
                'long_press_triggered': False,
                'short_press_handler': self.on_b2_short_press,
                'long_press_handler': self.on_b2_long_press
            }
        }
        self.none_symbol = [12,18,37,41,18,12]
        self.inverted_none_symbol = [243,237,218,214,237,243]
        self.ROW_HEIGHT = 12
        self.COL_WIDTH = 18
        self.START_X = 30
        self.START_Y = 1
        self.refresh_needed = True
        self.eq_engine = EquationEngine(DISP_W, DISP_H)
        self.display_ctrl = DisplayController(DISP_W, DISP_H)
        self.phase = 0.0
        self.freq = MIN_FREQ
        self.morph = 0.0
        self.last_target_morph = 0.0
        self.prev_waveform = []
        self.target_waveform = []
        self.selected_eq = None
        _thread.start_new_thread(self.cv_update_loop, ())

    def cv_update_loop(self):
        while True:
            if self.screen == 3:
                if self.selected_eq and self.selected_eq["title"] != "Logistic":
                    v = self.eq_engine.fold(sin(self.phase)*self.morph,1.0)
                    v_out = (v+1)*2.5
                    cv1.voltage(v_out)
                    cv2.voltage(5.0-v_out)
                self.phase = (self.phase + (self.freq/CV_RATE)*2*pi)%(2*pi)
            sleep_us(120)

    # -----------------------------------------------------------------------
    # buttons
    # -----------------------------------------------------------------------

    def check_button(self, button_id):
        b = self.buttons[button_id]
        p = b['pin']
        t = b['press_time']
        l = b['long_press_triggered']
        s = b['short_press_handler']
        g = b['long_press_handler']
        if p.value()==1:
            if t is None:
                b['press_time']=ticks_ms()
            else:
                d=ticks_ms()-t
                if d>=LONG_PRESS_DURATION and not l:
                    b['long_press_triggered']=True
                    g()
                    self.refresh_needed=True
        elif t is not None:
            d=ticks_ms()-t
            if d<LONG_PRESS_DURATION and not l:
                s()
                self.refresh_needed=True
            b['press_time']=None
            b['long_press_triggered']=False

    def on_b1_short_press(self):
        if self.screen==1:
            self.equation_index=(self.equation_index-1)%len(self.equations)
        elif self.screen==2:
            self.ctrl_index=(self.ctrl_index+1)%len(self.controls)
            eq_vars=self.equations[self.equation_index].get("vars",[])
            c=self.controls[self.ctrl_index]
            av=self.assignments[c]
            self.var_index=eq_vars.index(av)+1 if av in eq_vars else 0

    def on_b2_short_press(self):
        if self.screen==1:
            self.equation_index=(self.equation_index+1)%len(self.equations)
        elif self.screen==2:
            eq_data=self.equations[self.equation_index]
            eq_vars=eq_data.setdefault("vars",[])
            eq_asn=eq_data.setdefault("settings",{}).setdefault("assignments",{})
            total=len(eq_vars)+1
            c=self.controls[self.ctrl_index]
            oc="k2" if c=="k1" else "k1"
            n=0
            while n<total:
                self.var_index=(self.var_index+1)%total
                nv=eq_vars[self.var_index-1] if self.var_index else None
                cf=(c in["k1","k2"])and nv and eq_asn.get(oc)==nv
                if cf:
                    n+=1
                    continue
                break
            self.assignments[c]=nv
            eq_asn[c]=nv
            self.saveSettings()

    def on_b1_long_press(self):
        self.screen=(self.screen-1 if self.screen>1 else 3)
        self.saveSettings()

    def on_b2_long_press(self):
        self.screen=(self.screen+1 if self.screen<3 else 1)
        self.saveSettings()

    def saveSettings(self):
        try:
            with open("saved_state_Codex.txt", "r", encoding="utf-8") as f:
                d = json.load(f)

            d.setdefault("global_settings", {})["last_screen"] = self.screen
            d["global_settings"]["last_equation"] = self.equation_index  # store last equation index

            eq_list = d.get("equation_dict", [])
            if 0 <= self.equation_index < len(eq_list):
                eqd = eq_list[self.equation_index]
                eq_asn = eqd.setdefault("settings", {}).setdefault("assignments", {})
                for c in self.controls:
                    eq_asn[c] = self.assignments[c]

            with open("saved_state_Codex.txt", "w", encoding="utf-8") as f:
                json.dump(d, f)

        except Exception as e:
            print("[ERROR] Failed to save settings:", e)

    # -----------------------------------------------------------------------
    # rendering
    # -----------------------------------------------------------------------

    def draw_none_symbol(self,x,y,highlight=False):
        s=self.inverted_none_symbol if highlight else self.none_symbol
        for r,rd in enumerate(s):
            for c in range(6):
                oled.pixel(x+c,y+r,(rd>>(5-c))&1)

    def draw_inverted_text(self,t,x,y,w=None,h=10):
        w=len(t)*6 if w is None else w
        oled.fill_rect(x-2,y-2,w,h,1)
        oled.text(t,x,y,0)

    def draw_glyph(self,oled,g,x,y):
        for r,rd in enumerate(g["data"][:g["size"]]):
            for c in range(8):
                if(rd>>(7-c))&1:oled.pixel(x+c,y+r,1)
        return x+8

    def draw_token(self,oled,t,x,y):
        gf=self.byte_arrays.get(t)
        return self.draw_glyph(oled,gf,x,y)if gf else x

    def draw_equation_line(self,oled,text,x,y,tokens):
        px,i=x,0
        while i<len(text):
            for tk in tokens:
                if text.startswith(tk,i):
                    px=self.draw_token(oled,tk,px,y)
                    i+=len(tk)
                    break
            else:
                oled.text(text[i],px,y,1)
                px+=8
                i+=1

    # -----------------------------------------------------------------------
    # state = 1
    # -----------------------------------------------------------------------

    def display_home_screen(self):
        oled.fill(0)
        eqd=self.equations[self.equation_index]
        t=eqd["title"][:12]
        eq=eqd["equation"]
        toks=eqd["byte"]
        tx=(128-len(t)*8)//2
        oled.text(t,tx,0,1)
        if len(eq)>16:
            r1=eq[:16]
            r2=eq[16:]
            r1x=(128-len(r1)*8)//2
            r2x=(128-len(r2)*8)//2
            self.draw_equation_line(oled,r1,r1x,12,toks)
            self.draw_equation_line(oled,r2,r2x,24,toks)
        else:
            qx=(128-len(eq)*8)//2
            self.draw_equation_line(oled,eq,qx,12,toks)
        if ain.read_voltage()>0.1:
            oled.fill_rect(0,0,4,4,1)
        oled.show()

    # -----------------------------------------------------------------------
    # state = 2
    # -----------------------------------------------------------------------

    def display_assignment_screen(self):
        oled.fill(0)
        eqd=self.equations[self.equation_index]
        eq_vars=eqd.get("vars",[])
        eq_asn=eqd.get("settings",{}).get("assignments",{})
        for c in self.controls:
            if c in eq_asn:
                self.assignments[c]=eq_asn[c]
        for i,c in enumerate(self.controls):
            y=self.START_Y+i*self.ROW_HEIGHT
            if i==self.ctrl_index:
                self.draw_inverted_text(c,2,y,w=self.COL_WIDTH+10)
            else:
                oled.text(c,2,y,1)
            av=self.assignments[c]
            self.draw_none_symbol(self.START_X+5,y+2,highlight=(av is None or(i==self.ctrl_index and self.var_index==0)))
            for j,v in enumerate(eq_vars):
                x=self.START_X+(j+1)*self.COL_WIDTH
                if i==self.ctrl_index and self.var_index==j+1:
                    self.draw_inverted_text(v,x,y,w=self.COL_WIDTH-2,h=self.ROW_HEIGHT-2)
                elif av==v:
                    oled.fill_rect(x-2,y-2,self.COL_WIDTH-2,self.ROW_HEIGHT-2,1)
                    oled.text(v,x,y,0)
                else:
                    oled.text(v,x,y,1)
        oled.show()

    # -----------------------------------------------------------------------
    # state = 3
    # -----------------------------------------------------------------------

    def wave_engine_loop(self):
        if not self.equations: return
        while self.screen==3:
            for b in self.buttons:
                self.check_button(b)
            eqd=self.equations[self.equation_index]
            if eqd!=self.selected_eq:
                self.selected_eq=eqd
                self.phase=0.0
                self.prev_waveform=[]
                self.target_waveform=[]
                self.display_ctrl.interp=1.0
            ain_val=ain.read_voltage()
            ain_norm=0.0 if ain_val<0 else(1.0 if ain_val>5 else(ain_val/5.0))
            self.freq=MIN_FREQ+(MAX_FREQ-MIN_FREQ)*ain_norm
            c=self.equations[self.equation_index].get("settings",{}).get("assignments",{})
            k2var=c.get("k2")
            kv=round(k2.read_position(),2)
            if eqd["title"]=="Logistic" and k2var=="r":
                self.morph=2.5+(MAX_MORPH_LOGISTIC-2.5)*kv
            elif k2var=="amp":
                self.morph=MAX_MORPH_SINE*kv
            else:
                self.morph=MAX_MORPH_SINE*kv
            if abs(self.morph-self.last_target_morph)>TGT_TOL:
                nwf=self.eq_engine.compute_waveform(eqd,self.morph,self.freq)
                self.prev_waveform=self.display_ctrl.last_wave or nwf
                self.target_waveform=nwf
                self.display_ctrl.interp=0.0
                self.last_target_morph=self.morph
            if self.display_ctrl.interp<1.0:
                self.display_ctrl.interp=min(1.0,self.display_ctrl.interp+INTERP_STEP)
                wv=self.eq_engine.interp_waveform(self.prev_waveform,self.target_waveform,self.display_ctrl.interp)
                self.display_ctrl.render_waveform(wv,interp_active=True)
            else:
                if not self.target_waveform:
                    self.target_waveform=self.eq_engine.compute_waveform(eqd,self.morph,self.freq)
                self.display_ctrl.render_waveform(self.target_waveform)
            gc.collect()
            sleep_ms(SLEEP_MS)

    def main(self):
        self.refresh_needed=True
        while True:
            if self.screen==3:
                self.wave_engine_loop()
                self.refresh_needed=True
                continue
            for b in self.buttons:
                self.check_button(b)
            if self.refresh_needed:
                {1:self.display_home_screen,2:self.display_assignment_screen}.get(self.screen,lambda:None)()
                self.refresh_needed=False

if __name__=="__main__":
    Codex().main()
