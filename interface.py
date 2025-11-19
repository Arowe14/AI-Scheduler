import dearpygui.dearpygui as dpg
import os
from event import Event
from calendar_class import Calendar
import interpreter
from datetime import date, datetime, timedelta

today = date.today()
current_day = today
palette = [
    (200, 50, 50, 155),    # red
    (50, 200, 50, 155),    # green
    (50, 50, 200, 155),    # blue
    (200, 200, 50, 155),   # yellow
    (200, 50, 200, 155),   # magenta
    (50, 200, 200, 155),   # cyan
]
time_color = (255, 255, 255, 255) # WHITE
date_color = (200, 200, 200, 255) # LIGHT GREY
in_table_color = (200, 200, 200, 155) # FADED LIGHT GREY

TIME_COL_WIDTH = 60
HEADER_HEIGHT = 40

calendar_colors = {}

def get_calendar_color(name):
    if name not in calendar_colors:
        # Assign next color in palette (wrap around if needed)
        color = palette[len(calendar_colors) % len(palette)]
        calendar_colors[name] = color
    return calendar_colors[name]

def extend_without_duplicates(original_list, new_items):
    for item in new_items:
        if item.id not in {e.id for e in original_list}:
            original_list.append(item)
        elif item.summary not in {e.summary for e in original_list} and item.start not in {e.start for e in original_list}:
            original_list.append(item)
    return original_list

def remove_duplicates(list_a, list_b):
    ids_b = {item.id for item in list_b}
    summaries_b = {item.summary for item in list_b}
    starts_b = {item.start for item in list_b}

    filtered_a = [
        item for item in list_a
        if item.id not in ids_b and
           (item.summary not in summaries_b or item.start not in starts_b)
    ]
    return filtered_a
    
def adjust_input_height(sender, app_data):
    text = dpg.get_value(sender)
    lines = text.count("\n") + 1
    new_height = min(30 * lines, 120)  # Max height of 120
    dpg.configure_item(sender, height=new_height)

def get_chat_wrap():
    viewport_width = dpg.get_viewport_width()
    chat_width = int(viewport_width * 0.25)
    return max(120, chat_width - 24)

GRID_METRICS = {}
    
def run_interface(calendar: Calendar):
    calendar_names = calendar.get_calendar_names()
    calendar_colors = {name:  get_calendar_color(name) for name in calendar_names}

    dpg.create_context()
    dpg.create_viewport(title="Scheduler AI - Chat Interface", width=1000, height=700)
    dpg.setup_dearpygui()

    user_color = (0, 150, 255, 255)
    ai_color   = (0, 200, 100, 255)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(BASE_DIR, "Fonts", "FindSansPro-Light.ttf")

    chat_text_items = []
    event_list = []

    to_delete_events = []
    to_add_events = []
    already_added_events = []

    # -------------------------------
    # Message sending
    # -------------------------------
    def send_message(input_id, chat_area):
        nonlocal event_list, to_add_events, to_delete_events
        text = dpg.get_value(input_id).strip()
        if text:
            wrap = get_chat_wrap()
            txt_user = dpg.add_text(f"{text}", parent=chat_area,
                                    color=user_color, wrap=wrap)
            chat_text_items.append(txt_user)
            dpg.set_value(input_id, "")
            dpg.configure_item(input_id, height=30)

            events = process_multiline_input(text)
            event_list, to_add, to_delete = calendar.schedule_events(events, event_list)

            for event in to_delete:
                print("Deleting event from display:", event.summary, event.start)
            event_list = remove_duplicates(event_list, to_delete)
            

            for event in to_add:
                txt_ai = dpg.add_text(
                    f"{event.summary} scheduled on {event.start.strftime('%A, %B %d, %Y from %I:%M %p')} to {event.end.strftime('%I:%M %p')}",
                    parent=chat_area, color=ai_color, wrap=wrap
                )
                chat_text_items.append(txt_ai)

            event_list.extend(events)
            to_add_events.extend(to_add)
            to_delete_events.extend(to_delete)

            draw_events(current_day)
            calendar.save_events(event_list, filename="events.json")

            dpg.add_text("Any other events?", parent=chat_area,
            color=ai_color, wrap=wrap)


    # -------------------------------
    # Enter key handling
    # -------------------------------
    def handle_enter():
        send_message("user_input", "chat_message_area")
        # Clear the text box and reset height
        dpg.set_value("user_input", "")
        dpg.configure_item("user_input", height=30)

    # -------------------------------
    # Fonts
    # -------------------------------
    with dpg.font_registry():
        main_font = dpg.add_font(font_path, 24)
        small_font = dpg.add_font(font_path, 16)
    dpg.bind_font(main_font)

    # -------------------------------
    # Build UI
    # -------------------------------
    with dpg.window(label="Scheduler AI", tag="main_window"):
        with dpg.child_window(tag="main_container"):
            with dpg.group(horizontal=True):
                # Left panel
                with dpg.group(horizontal=False):
                    # Scrollable chat messages
                    with dpg.child_window(tag="chat_message_area", border=False):
                        txt1 = dpg.add_text("Welcome to your Scheduler!", color=ai_color, wrap=0)
                        txt2 = dpg.add_text("Describe an event you would like to add to your Google Calendar.", color=ai_color, wrap=0)
                        chat_text_items.extend([txt1, txt2])

                    # Fixed input bar
                    with dpg.child_window(tag="chat_input_area", border=False):
                        with dpg.table(header_row=False, resizable=True, policy=dpg.mvTable_SizingStretchProp):
                            dpg.add_table_column()
                            dpg.add_table_column(width_fixed=True, width=90)
                            with dpg.table_row():
                                user_input = dpg.add_input_text(
                                    tag="user_input",
                                    width=-1,
                                    height=30,
                                    hint="Type your task or command...",
                                    callback=adjust_input_height,
                                    on_enter=True,
                                )
                                dpg.add_button(
                                    label="Send",
                                    width=90,
                                    callback=lambda: send_message("user_input", "chat_message_area"),
                                )

                            with dpg.handler_registry():
                                dpg.add_key_press_handler(dpg.mvKey_Return, callback=handle_enter)


                # Middle panel
                with dpg.child_window(tag="calendar_window", border=True):
                    # Just define the drawlist; actual drawing happens in _on_resize
                    with dpg.drawlist(tag="calendar_grid", width=800, height=600):
                        pass
                
                # Right button panel
                with dpg.child_window(tag="button_panel", border=False):
                    dpg.add_text("Legend:")
                    with dpg.group(horizontal=False):
                        for name, color in calendar_colors.items():
                           with dpg.group(horizontal=True):
                                with dpg.drawlist(width=20, height=20):
                                    dpg.draw_rectangle((0,0), (20,20), color=color, fill=color)
                                dpg.add_text(name, tag=f"legend_{color}", wrap=150)
                    dpg.add_spacer(height=20)
                            
                    with dpg.table(header_row=False):
                        dpg.add_table_column()
                        dpg.add_table_column()
                        with dpg.table_row():
                            dpg.add_button(tag="previous_week",
                                label="Previous Week", 
                                height=35, 
                                callback=lambda: previous_week()
                            )
                            dpg.bind_item_font("previous_week", small_font)
                            dpg.add_button(tag="next_week", 
                                label="Next Week", 
                                height=35, 
                                callback=lambda: next_week()
                            )
                            dpg.bind_item_font("next_week", small_font)
                    dpg.add_button(
                        label="Get Events from Calendar",
                        width=-1,   # stretch to full width of child window
                        height=35,
                        callback=lambda: get_events(current_day)
                    )
                    dpg.add_button(
                        label="Add to Google Calendar",
                        width=-1,   # stretch to full width of child window
                        height=35,
                        callback=lambda: add_events(to_add_events)  # define this function
                    )

    def _on_resize(sender, app_data):
        """Adjust layout on viewport resize. Also the initial draw."""
        w = dpg.get_viewport_width() - 50
        h = dpg.get_viewport_height() - 15

        # Resize main containers
        dpg.configure_item("main_window", width=w, height=h)
        dpg.configure_item("main_container", width=w, height=h - 40)

        new_chat_width = int(w * 0.25)
        message_height = h - 100
        dpg.configure_item("chat_message_area", width=new_chat_width, height=message_height)
        dpg.configure_item("chat_input_area", width=new_chat_width, height=0)

        # Calendar window/drawlist
        cal_width = int(w * 0.6)
        cal_height = h - 60
        grid_height = cal_height - 18

        dpg.configure_item("calendar_window", width=cal_width, height=cal_height)
        dpg.configure_item("calendar_grid", width=cal_width, height=grid_height)

        days = 7
        header_height = 50
        hours = 24

        # First column slimmer
        time_col_width = 80
        day_col_width = (cal_width - time_col_width) / days
        hour_height = (grid_height - header_height) / hours

        # Clear old drawings
        dpg.delete_item("calendar_grid", children_only=True)

        # Vertical lines (time column + day columns)
        dpg.draw_line((time_col_width, 0), (time_col_width, grid_height),
                    color=(200, 200, 200, 255), parent="calendar_grid")
        for i in range(days + 1):
            x = time_col_width + i * day_col_width
            dpg.draw_line((x, 0), (x, grid_height), color=(200, 200, 200, 255), parent="calendar_grid")
        # Horizontal lines
        # Top line
        dpg.draw_line((0, 0), (cal_width, 0), color=(200, 200, 200, 255), parent="calendar_grid")
        # Header bottom line
        dpg.draw_line((0, header_height), (cal_width, header_height), color=(200, 200, 200, 255), parent="calendar_grid")
        # Hour rows
        for h_idx in range(hours):
            y = header_height + (h_idx + 1) * hour_height
            dpg.draw_line((0, y), (cal_width, y), color=(200, 200, 200, 255), parent="calendar_grid")
        
        dpg.draw_text((5, 10), "Time", size=16, color=date_color, parent="calendar_grid")
        # Row 0 → day labels
        for i in range(days):
            day = current_day + timedelta(days=i)
            label = day.strftime("%A\n%B %d")
            dpg.draw_text((time_col_width + i * day_col_width + 5, 10),
                        label, size=16, color=date_color, parent="calendar_grid")

        # Rows 1–24 → hour labels in first column
        for h_idx in range(hours):
            y = header_height + h_idx * hour_height
            hour_12 = (h_idx % 12) or 12
            suffix = "AM" if h_idx < 12 else "PM"
            label = f"{hour_12}:00{suffix}"

            dpg.draw_text((5, y + 5), label, size=16, color=time_color, parent="calendar_grid")



        GRID_METRICS.update({
            "cal_width": cal_width, "cal_height": grid_height,
            "header_height": header_height, "time_col_width": time_col_width,
            "hour_height": hour_height, "day_col_width": day_col_width
        })
        # Redraw events
        draw_events(current_day)
        
        
        # Button panel
        dpg.configure_item("button_panel", width=w*0.15, height=cal_height)
        dpg.configure_item("previous_week", width=w*.15//2)
        dpg.configure_item("next_week", width=w*.15//2)
        for legend in calendar_names:
            color = calendar_colors.get(legend, (100, 100, 100, 155))
            dpg.configure_item(f"legend_{color}", wrap=w*0.15 - 10)

    drawn_events = []
    def draw_events(current_day):
        nonlocal event_list, drawn_events

        # Clear only previously drawn event rectangles/text
        for item_id in drawn_events:
            if dpg.does_item_exist(item_id):
                dpg.delete_item(item_id)
        drawn_events.clear()

        for event in event_list:
            day_offset = (event.start.date() - current_day).days
            if not (0 <= day_offset < 7):
                continue

            start_hour, start_min = event.start.hour, event.start.minute
            end_hour, end_min = event.end.hour, event.end.minute

            m = GRID_METRICS

            x1 = m["time_col_width"] + day_offset * m["day_col_width"]
            x2 = m["time_col_width"] + (day_offset + 1) * m["day_col_width"]

            y1 = m["header_height"] + start_hour * m["hour_height"] + (start_min / 60) * m["hour_height"]
            y2 = m["header_height"] + end_hour * m["hour_height"] + (end_min / 60) * m["hour_height"]

            color = calendar_colors.get(event.calendar_name, (100, 100, 100, 175))
            rect_id = dpg.draw_rectangle((x1, y1), (x2, y2), color=color, fill=color, parent="calendar_grid")
            text_id = dpg.draw_text((x1 + 5, y1 + 5), event.summary, size=16,
                                    color=(255, 255, 255, 255), parent="calendar_grid")

            # Track what you just drew
            drawn_events.extend([rect_id, text_id])

    def add_events(events):
        for event in events:
            print("Adding event to Google Calendar:", event.summary, event.start)
        calendar.add_events(events)
        
    def get_events(current_day):
        nonlocal event_list
        wrap = get_chat_wrap()
        dpg.add_text(f"Fetching calendar data until {current_day + timedelta(days=7)}...", parent="chat_message_area",
            color=ai_color, wrap=wrap)
        for i in range(7):
            already_added_events = calendar.get_events(current_day+timedelta(days=i))
            calendar.save_events(already_added_events, filename="events.json")
            event_list = extend_without_duplicates(event_list, already_added_events)
            draw_events(current_day)
        dpg.add_text("Events fetched and displayed.", parent="chat_message_area",
            color=ai_color, wrap=wrap)

    
    def process_multiline_input(text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        results = []
        for line in lines:
            event = interpreter.interpret_input(calendar_names, line)
            print("Interpreted Event:", event.summary, event.date)
            results.append(event)
        return results


    def previous_week():
        global current_day
        current_day -= timedelta(days=7)
        _on_resize(None, None)

    def next_week():
        global current_day
        current_day += timedelta(days=7)
        _on_resize(None, None)

    dpg.set_viewport_resize_callback(_on_resize)
    _on_resize(None, None)

    dpg.set_primary_window("main_window", True)
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()