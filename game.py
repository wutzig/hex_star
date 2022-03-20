from dataclasses import dataclass, field
import math
from queue import PriorityQueue
import pygame
import pygame.gfxdraw

POINTER_OFFSET   = 0.09
BACKGROUND_COLOR = (80,80,80)
SELECT_COLOR     = (200,200,200)
PLAYER_COLOR     = (80,80,80)
GRID_OFFSET      = 5
PLAYER_SPEED     = 1.0
HEX_COLORS       = (
    (180,120,120),
    (120,180,120),
    (120,120,180)
)
HEX_HEIGHT = 64
GRID_HEIGHT = 13
GRID_WIDTH = 13

quart_height = HEX_HEIGHT / 4
three_quart_height = 3 * quart_height
hex_width = HEX_HEIGHT * math.sqrt(3) / 2
half_width = hex_width / 2
hex_vertices = [
    (half_width, 0), 
    (hex_width, quart_height), 
    (hex_width, three_quart_height), 
    (half_width, HEX_HEIGHT),
    (0, three_quart_height),
    (0, quart_height)
]

game_running = True
draw_edges   = True
class Hexagon:
    pass

@dataclass
class HexGrid:
    height:   int                 = field(init=True, compare=True)
    width:    int                 = field(init=True, compare=True)
    hexagons: list[list[Hexagon]] = field(init=False,compare=False,default_factory=list)
    selected_hex: Hexagon         = None
    
    def __post_init__(self):
        self.hexagons = [
            [Hexagon(HEX_COLORS[(j + 2*(i%2)) % 3], (j,i)) for j in range(self.width - (i%2))] 
            for i in range(self.height) 
        ]
        for irow, row in enumerate(self.hexagons):
            odd_row = irow % 2
            for icol, hex in enumerate(row):
                left  = icol + odd_row - 1
                right = icol + odd_row
                hex.neighbors.up_left    = self[irow-1, left]
                hex.neighbors.up_right   = self[irow-1, right]
                hex.neighbors.down_left  = self[irow+1, left]
                hex.neighbors.down_right = self[irow+1, right]
                hex.neighbors.left       = self[irow, icol-1]
                hex.neighbors.right      = self[irow, icol+1]


    def __getitem__(self, key: tuple[int]) -> Hexagon:
        if key[0] < 0 or key[0] >= len(self.hexagons): return None
        if key[1] < 0 or key[1] >= len(self.hexagons[key[0]]): return None
        return self.hexagons[key[0]][key[1]]

    def draw(self):
        for row in self.hexagons:
            for hex in row:
                hex.draw()

class NeighborhoodIter:
    def __init__(self, neighbors: list[Hexagon]) -> None:
        self.neighbors = neighbors
        self.index = 0
    def __next__(self) -> Hexagon:
        if self.index < len(self.neighbors):
            result = self.neighbors[self.index]
            self.index += 1
            return result
        else:
            raise StopIteration
@dataclass
class HexNeighborhood:
    left:       Hexagon = None
    right:      Hexagon = None
    up_left:    Hexagon = None
    up_right:   Hexagon = None
    down_left:  Hexagon = None
    down_right: Hexagon = None

    def __iter__(self):
        return NeighborhoodIter([n for n in [self.up_left, self.up_right, self.right, self.down_right, self.down_left, self.left] if n])

@dataclass(unsafe_hash=True)
class Hexagon:
    color:       tuple[int]       = field(compare=False, hash=False)
    position:    tuple[int]       = field(compare=True, repr=True, hash=True)
    vertices:    list[tuple[int]] = field(init=False, compare=False, default_factory=list, hash=False)
    center:      tuple[float]     = field(init=False, compare=False, hash=False)
    neighbors:   HexNeighborhood  = field(init=False, compare=False, default_factory=HexNeighborhood, hash=False)
    highlighted: bool             = False
    blocked:     bool             = False
    
    def __post_init__(self):
        self.vertices = [(
            v[0] + GRID_OFFSET + self.position[0] * hex_width + (self.position[1] % 2 * half_width), 
            v[1] + GRID_OFFSET + self.position[1] * three_quart_height)
        for v in hex_vertices]
            
        self.center = (self.vertices[0][0], (self.vertices[1][1] + self.vertices[2][1]) / 2.0)
    
    def draw(self):
        face_color = BACKGROUND_COLOR if self.blocked else SELECT_COLOR if self.highlighted else self.color
        edge_color = (0,0,0) if draw_edges else face_color
        pygame.draw.polygon(screen, face_color, self.vertices, 0)
        pygame.gfxdraw.aapolygon(screen, self.vertices, edge_color)

@dataclass
class Player:
    color:    tuple[int]    = field(compare=False)
    position: Hexagon       = field(compare=False)
    hex_grid: HexGrid       = field(compare=False)
    center:   tuple[float]  = field(compare=False, init=False)
    path:     list[Hexagon] = field(compare=False, init=False, default_factory=list)
    _destination: Hexagon   = None

    @property
    def destination(self) -> Hexagon:
        return self._destination

    @destination.setter
    def destination(self, new_dest: Hexagon) -> None:
        if not new_dest.blocked:
            self._destination = new_dest
            self.find_path()

    def __post_init__(self):
        self.center = self.position.center
    
    def draw(self):
        pygame.draw.circle(screen, self.color, self.center, quart_height)
        if len(self.path) > 1:
            pygame.draw.lines(screen, self.color, False, [hexagon.center for hexagon in self.path], 3)
    
    def move(self, position_hex: Hexagon):
        if position_hex and not position_hex.blocked:
            self.position = position_hex
            self.center = position_hex.center
            self.find_path()

    def find_path(self) -> None:
        '''A* path finding. Sets player's path to current destination.'''
        def h(a: Hexagon, b: Hexagon) -> float:
            return math.fabs(a.position[0] - b.position[0]) + math.fabs(a.position[1] - b.position[1])
        
        if self.destination:
            came_from = {self.position: None}
            self.path = []

            q_count = 0
            q = PriorityQueue()
            q.put((0, q_count, self.position))
            open_nodes = {self.position}
            
            f_score = {node: math.inf for row in self.hex_grid.hexagons for node in row}
            f_score[self.position] = h(self.position, self.destination)
            
            g_score = {node: math.inf for row in self.hex_grid.hexagons for node in row}
            g_score[self.position] = 0

            while not q.empty():
                current_node = q.get()[2]
                open_nodes.remove(current_node)
                if current_node == self.destination:
                    while current_node:
                        self.path.insert(0, current_node)
                        current_node = came_from[current_node]
                    return True
                for neighbor in [n for n in current_node.neighbors if not n.blocked]:
                    score = g_score[current_node] + 1
                    if score < g_score[neighbor]:
                        g_score[neighbor] = score
                        f_score[neighbor] = score + h(neighbor, self.destination)
                        came_from[neighbor] = current_node
                        if neighbor not in open_nodes:
                            open_nodes.add(neighbor)
                            q_count += 1
                            q.put((f_score[neighbor], q_count, neighbor))
        return False
            


if __name__ == '__main__':
    hex_grid = HexGrid(GRID_HEIGHT,GRID_WIDTH)
    player   = Player(PLAYER_COLOR, hex_grid[0, 0], hex_grid)

    pygame.init()
    pygame.display.set_caption('Hex_star')
    pygame.display.set_icon(pygame.image.load('res/icon.png'))

    disp_width = math.ceil(hex_width * hex_grid.width + 2 * GRID_OFFSET)
    disp_height = three_quart_height * hex_grid.height + quart_height + 2 * GRID_OFFSET
    screen = pygame.display.set_mode(size = (disp_width, disp_height))

    frames = 0
    delta_time = 0
    clock = pygame.time.Clock()
    while game_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and hex_grid.selected_hex: #left click on selected hex
                    player.destination = hex_grid.selected_hex
                if event.button == 3 and hex_grid.selected_hex: #left click on selected hex
                    hex_grid.selected_hex.blocked = not hex_grid.selected_hex.blocked
                    player.find_path()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game_running = False
                elif event.key == pygame.K_g:
                    draw_edges = not draw_edges
                elif event.key == pygame.K_d:
                    player.move(player.position.neighbors.right)
                elif event.key == pygame.K_a:
                    player.move(player.position.neighbors.left)
                elif event.key == pygame.K_x:
                    player.move(player.position.neighbors.down_right)
                elif event.key == pygame.K_z:
                    player.move(player.position.neighbors.down_left)
                elif event.key == pygame.K_w:
                    player.move(player.position.neighbors.up_right)
                elif event.key == pygame.K_q:
                    player.move(player.position.neighbors.up_left)
            elif event.type == pygame.MOUSEMOTION:
                mouse_x      = event.pos[0] - GRID_OFFSET
                mouse_y      = event.pos[1] - GRID_OFFSET
                relative_row = mouse_y / three_quart_height
                row_fract    = relative_row % 1
                mouse_row    = math.floor(relative_row)
                odd_row      = mouse_row % 2
                
                relative_col = (mouse_x - odd_row * half_width) / hex_width
                col_fract    = 0.5 - (relative_col % 1)
                mouse_col    = math.floor(relative_col)

                if 2 * row_fract < math.fabs(col_fract) + POINTER_OFFSET:
                    odd_row = 1 - odd_row
                    mouse_row -= 1
                    mouse_col += (col_fract < 0) - odd_row

                mouse_hex = hex_grid[mouse_row, mouse_col]
                if hex_grid.selected_hex != mouse_hex:
                    if hex_grid.selected_hex:
                        hex_grid.selected_hex.highlighted = False
                        for neighbor in hex_grid.selected_hex.neighbors:
                            neighbor.highlighted = False
        
                    hex_grid.selected_hex = mouse_hex
                    if hex_grid.selected_hex:                
                        hex_grid.selected_hex.highlighted = True
                        for neighbor in hex_grid.selected_hex.neighbors:
                            neighbor.highlighted = True

        # clock.tick()
        # print(f'\r{int(clock.get_fps())}', end='')

        screen.fill(color=BACKGROUND_COLOR)
        hex_grid.draw()
        player.draw()
        pygame.display.update()

    pygame.quit()