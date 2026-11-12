import csv
import glob
import os
import re
from PIL import Image
import networkx as nx

# --- Configuration ---
PROVINCES_BMP = "provinces.bmp"
DEFINITION_CSV = "definition.csv"
STATES_DIR = "../history/states"
SUPPLY_NODES_TXT = "supply_nodes.txt"
OUTPUT_RAILWAYS_TXT = "railways.txt"
DEFAULT_RAILWAY_LEVEL = 1


def load_definitions(csv_path):
    """Maps RGB color tuples to land province IDs from definition.csv."""
    rgb_to_id = {}
    land_ids = set()
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if not row or len(row) < 5:
                continue
            try:
                prov_id = int(row.pop(0))
                r = int(row.pop(0))
                g = int(row.pop(0))
                b = int(row.pop(0))
                prov_type = row.pop(0).strip().lower()
                if prov_id > 0 and prov_type == "land":
                    rgb_to_id[(r, g, b)] = prov_id
                    land_ids.add(prov_id)
            except ValueError:
                continue
    return rgb_to_id, land_ids


def build_province_graph(bmp_path, rgb_to_id):
    """Builds an adjacency graph of land provinces from provinces.bmp."""
    img = Image.open(bmp_path).convert("RGB")
    width, height = img.size
    pixels = img.load()

    G = nx.Graph()
    prov_grid = [[None] * width for _ in range(height)]

    for y in range(height):
        for x in range(width):
            prov_id = rgb_to_id.get(pixels[x, y])
            prov_grid[y][x] = prov_id
            if prov_id is not None:
                G.add_node(prov_id)

    for y in range(height):
        for x in range(width):
            p1 = prov_grid[y][x]
            if p1 is None:
                continue
            if x + 1 < width:
                p2 = prov_grid[y][x + 1]
                if p2 is not None and p1 != p2:
                    G.add_edge(p1, p2)
            if y + 1 < height:
                p3 = prov_grid[y + 1][x]
                if p3 is not None and p1 != p3:
                    G.add_edge(p1, p3)

    return G


def generate_supply_nodes_from_states(states_dir, land_ids):
    """Scans history/states/*.txt for victory points or state capitals to build supply_nodes.txt."""
    nodes = []
    state_files = sorted(glob.glob(os.path.join(states_dir, "*.txt")))
    
    for filepath in state_files:
        with open(filepath, mode="r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()

        # Look for victory_points = { <prov_id> <value> }
        vp_matches = re.findall(r"victory_points\s*=\s*\{\s*(\d+)", content)
        found_in_state = False
        for prov_str in vp_matches:
            prov_id = int(prov_str)
            if prov_id in land_ids and prov_id not in nodes:
                nodes.append(prov_id)
                found_in_state = True

        # Fallback: pick the first valid land province in the state if no VPs exist
        if not found_in_state:
            provs_block = re.search(r"provinces\s*=\s*\{([^}]+)\}", content)
            if provs_block:
                for token in provs_block.group(1).split():
                    if token.isdigit():
                        prov_id = int(token)
                        if prov_id in land_ids and prov_id not in nodes:
                            nodes.append(prov_id)
                            break

    with open(SUPPLY_NODES_TXT, mode="w", encoding="utf-8") as f:
        for prov_id in nodes:
            f.write(f"1 {prov_id}\n")

    print(f"Created {SUPPLY_NODES_TXT} with {len(nodes)} nodes from state files.")
    return nodes


def load_supply_nodes(nodes_path, land_ids):
    """Reads valid land supply node province IDs from supply_nodes.txt."""
    if not os.path.exists(nodes_path):
        print(f"{nodes_path} not found. Generating from {STATES_DIR}...")
        return generate_supply_nodes_from_states(STATES_DIR, land_ids)

    nodes = []
    with open(nodes_path, mode="r", encoding="utf-8-sig") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
                parts.pop(0)
                prov_id = int(parts.pop(0))
                if prov_id in land_ids and prov_id not in nodes:
                    nodes.append(prov_id)
    return nodes


def generate_railways():
    print("Loading definition.csv...")
    rgb_to_id, land_ids = load_definitions(DEFINITION_CSV)

    print("Scanning provinces.bmp for adjacencies...")
    G = build_province_graph(PROVINCES_BMP, rgb_to_id)

    print("Loading or generating supply nodes...")
    nodes = load_supply_nodes(SUPPLY_NODES_TXT, land_ids)
    if len(nodes) < 2:
        print("Error: Need at least 2 valid land supply nodes. Check your history/states files.")
        return

    print(f"Found {len(nodes)} supply nodes. Computing shortest railway network...")
    meta_graph = nx.Graph()
    shortest_paths = {}

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            try:
                path = nx.shortest_path(G, source=u, target=v)
                meta_graph.add_edge(u, v, weight=len(path))
                shortest_paths[(u, v)] = path
                shortest_paths[(v, u)] = list(reversed(path))
            except nx.NetworkXNoPath:
                continue

    mst = nx.minimum_spanning_tree(meta_graph)

    lines = []
    for u, v in mst.edges():
        path = shortest_paths[(u, v)]
        if len(path) >= 2:
            path_str = " ".join(str(p) for p in path)
            lines.append(f"{DEFAULT_RAILWAY_LEVEL} {len(path)} {path_str}")

    with open(OUTPUT_RAILWAYS_TXT, mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Done! Generated {len(lines)} railway lines in {OUTPUT_RAILWAYS_TXT}.")


if __name__ == "__main__":
    generate_railways()
