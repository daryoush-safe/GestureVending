import cv2

# Default Layout (can be overwritten by update_grid_layout)
# Logic: integers represent number of columns in that row
grid_layout = [] 

def update_grid_layout(config):
    """
    Regenerates the grid_layout list based on new MQTT config logic.
    """
    global grid_layout
    try:
        total_slots = int(config.get('NumOfSlots', 60))
        # "NumOfDoubleSlots" in user logic = Count of rows with 10 objects
        num_10_col_rows = int(config.get('NumOfDoubleSlots', 0))
        
        # Calculate total rows (always groups of 10 IDs per row)
        total_rows = total_slots // 10
        
        # Calculate how many top rows are 5-column (the "others")
        num_5_col_rows = total_rows - num_10_col_rows
        
        new_layout = []
        
        # 1. Fill Top Rows (5 columns, IDs 0, 2, 4, 6, 8)
        for _ in range(num_5_col_rows):
            new_layout.append(5)
            
        # 2. Fill Bottom Rows (10 columns, IDs 0-9)
        for _ in range(num_10_col_rows):
            new_layout.append(10)
        
        grid_layout = new_layout
        print(f"Grid Layout Updated: {grid_layout} (Total Rows: {total_rows})")
        
    except Exception as e:
        print(f"Error parsing grid config: {e}")
        # Fallback default if error
        grid_layout = [5, 10, 10, 10, 10, 10]

def get_grid_cell(x, y, width, height):
    global grid_layout
    num_rows = len(grid_layout)
    if num_rows == 0: return (0, 0, 1)
    
    row_height = height / num_rows
    
    # 1. Determine Row
    row = int(y / row_height)
    if row >= num_rows: row = num_rows - 1
    if row < 0: row = 0

    # 2. Determine Column based on specific configuration of THIS row
    cols_in_this_row = grid_layout[row]
    col_width = width / cols_in_this_row
    
    col = int(x / col_width)
    if col >= cols_in_this_row: col = cols_in_this_row - 1
    if col < 0: col = 0
    
    return (row, col, cols_in_this_row)

def calculate_slot_id(row, col):
    """
    Calculates Slot ID based on Row and Col.
    Rows are always indexed in blocks of 10.
    
    - If Row is 5-col: Col 0->ID 0, Col 1->ID 2, Col 2->ID 4...
    - If Row is 10-col: Col 0->ID 0, Col 1->ID 1...
    """
    global grid_layout
    if row >= len(grid_layout): return 0

    cols_in_row = grid_layout[row]
    
    # Base ID is always row * 10 (e.g., Row 0 starts at 0, Row 1 starts at 10)
    base_id = row * 10
    
    if cols_in_row == 5:
        # Wide slots (Index 0, 2, 4, 6, 8)
        offset = col * 2
    else:
        # Standard slots (Index 0, 1, 2...9)
        offset = col
        
    return base_id + offset

def draw_grid(frame):
    global grid_layout
    height, width, _ = frame.shape
    num_rows = len(grid_layout)
    if num_rows == 0: return

    row_height = height / num_rows
    
    # Draw Horizontal lines
    for i in range(1, num_rows):
        y = int(i * row_height)
        cv2.line(frame, (0, y), (width, y), (255, 255, 255), 1)
    
    # Draw Vertical lines
    for r in range(num_rows):
        cols = grid_layout[r]
        col_width = width / cols
        y_start = int(r * row_height)
        y_end = int((r + 1) * row_height)
        
        for c in range(1, cols):
            x = int(c * col_width)
            cv2.line(frame, (x, y_start), (x, y_end), (255, 255, 255), 1)