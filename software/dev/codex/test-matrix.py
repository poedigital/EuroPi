from europi import *
from time import sleep

controls = ["ain","k1","k2"]
variables = ["a","b","c","z","w"]
assignments = {c:None for c in controls}
ctrl_index = 0
var_index = 0
none_symbol = [12,18,37,41,18,12]
inverted_none_symbol = [243,237,218,214,237,243]
ROW_HEIGHT = 12
COL_WIDTH = 18
START_X = 30
START_Y = 1

def draw_none_symbol(oled,x,y,highlight=False):
    s = inverted_none_symbol if highlight else none_symbol
    for row,rd in enumerate(s):
        for col in range(6):
            oled.pixel(x+col,y+row,(rd>>(5-col))&1)

def draw_inverted_text(oled,text,x,y,box_width=None,box_height=ROW_HEIGHT-2):
    box_width = box_width or len(text)*6
    oled.fill_rect(x-3,y-2,box_width,box_height,1)
    oled.text(text,x,y,0)

def display_matrix():
    oled.fill(0)
    for i,control in enumerate(controls):
        y = START_Y + i*ROW_HEIGHT
        if i == ctrl_index:
            draw_inverted_text(oled,control,2,y,box_width=COL_WIDTH+10)
        else:
            oled.text(control,2,y,1)
        assigned = assignments[control]
        none_highlight = (assigned is None) or (var_index == 0 and i == ctrl_index)
        draw_none_symbol(oled,START_X+5,y+2,none_highlight)
        for j,var in enumerate(variables):
            x = START_X + (j+1)*COL_WIDTH
            if var_index == j+1 and i == ctrl_index:
                draw_inverted_text(oled,var,x,y,box_width=COL_WIDTH-2)
            elif assigned == var:
                oled.fill_rect(x-2,y-2,COL_WIDTH-2,ROW_HEIGHT-2,1)
                oled.text(var,x,y,0)
            else:
                oled.text(var,x,y,1)
    oled.show()

def check_buttons():
    global ctrl_index,var_index
    if b1.value():
        ctrl_index = (ctrl_index + 1) % len(controls)
        assigned_var = assignments[controls[ctrl_index]]
        var_index = variables.index(assigned_var) + 1 if assigned_var else 0
    if b2.value():
        while True:
            var_index = (var_index + 1) % (len(variables) + 1)
            new_assignment = None if var_index == 0 else variables[var_index - 1]
            if (controls[ctrl_index] == "k1" and assignments["k2"] == new_assignment and new_assignment) or \
               (controls[ctrl_index] == "k2" and assignments["k1"] == new_assignment and new_assignment):
                continue
            break
        assignments[controls[ctrl_index]] = new_assignment

def main():
    while True:
        check_buttons()
        display_matrix()
        sleep(0.1)

if __name__ == "__main__":
    main()