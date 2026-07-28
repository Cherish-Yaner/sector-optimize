from section import Section
from typing import List, Dict, Set
from polygon import HexGrid

# 假设 hexes 是 HexGrid 列表，每个 HexGrid 有 neighbors 属性，值为 dict[str, Optional[int]]
def build_section_graph(section: Section, hexes: List["HexGrid"]) -> Dict[int, Set[int]]:
    graph = {idx: set() for idx in section.grid_list}
    for idx in section.grid_list:
        grid = hexes[idx]
        for _, neighbor in grid.neighbors.items():
            if neighbor is not None and hexes[neighbor].section == section.index:
                graph[idx].add(neighbor)
    return graph

def find_articulation_points(graph: Dict[int, Set[int]]) -> Set[int]:
    time = [0]
    low = {}
    dfn = {}
    parent = {}
    ap = set()

    def dfs(u: int):
        children = 0
        time[0] += 1
        dfn[u] = low[u] = time[0]
        for v in graph[u]:
            if v not in dfn:
                parent[v] = u
                children += 1
                dfs(v)  # 递归调用dfs
                low[u] = min(low[u], low[v])
                if parent.get(u) is None and children > 1:  # 如果 u 是根节点且 u 有两个或以上的子节点，则 u 是割点
                    ap.add(u)
                if parent.get(u) is not None and low[v] >= dfn[u]:  # 如果 u 不是根节点且 low[v] 大于或等于 dfn[u]，则 u 是割点
                    ap.add(u)
            elif v != parent.get(u):  # 如果 v 已被访问且不是 u 的父节点，则更新 low[u]
                low[u] = min(low[u], dfn[v])

    for node in graph:
        if node not in dfn:
            dfs(node)

    return ap

def compute_section_articulation_points(section: Section, hexes: List["HexGrid"]) -> Set[int]:
    graph = build_section_graph(section, hexes)
    return find_articulation_points(graph)