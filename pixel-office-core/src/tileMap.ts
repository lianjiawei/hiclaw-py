import type { TileType } from './types.js';
import { TileType as Tile } from './types.js';

export function isWalkable(col: number, row: number, tileMap: TileType[][], blockedTiles: Set<string>): boolean {
  const rows = tileMap.length;
  const cols = rows > 0 ? tileMap[0].length : 0;
  if (row < 0 || row >= rows || col < 0 || col >= cols) return false;
  const tile = tileMap[row][col];
  if (tile === Tile.WALL || tile === Tile.VOID) return false;
  if (blockedTiles.has(`${col},${row}`)) return false;
  return true;
}

export function getWalkableTiles(tileMap: TileType[][], blockedTiles: Set<string>): Array<{ col: number; row: number }> {
  const rows = tileMap.length;
  const cols = rows > 0 ? tileMap[0].length : 0;
  const tiles: Array<{ col: number; row: number }> = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (isWalkable(c, r, tileMap, blockedTiles)) tiles.push({ col: c, row: r });
    }
  }
  return tiles;
}

export function findPath(startCol: number, startRow: number, endCol: number, endRow: number, tileMap: TileType[][], blockedTiles: Set<string>): Array<{ col: number; row: number }> {
  if (startCol === endCol && startRow === endRow) return [];
  if (!isWalkable(endCol, endRow, tileMap, blockedTiles)) return [];
  const key = (c: number, r: number) => `${c},${r}`;
  const startKey = key(startCol, startRow);
  const endKey = key(endCol, endRow);
  const visited = new Set<string>([startKey]);
  const parent = new Map<string, string>();
  const queue: Array<{ col: number; row: number }> = [{ col: startCol, row: startRow }];
  const dirs = [
    { dc: 0, dr: -1 },
    { dc: 0, dr: 1 },
    { dc: -1, dr: 0 },
    { dc: 1, dr: 0 },
  ];
  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentKey = key(current.col, current.row);
    if (currentKey === endKey) {
      const path: Array<{ col: number; row: number }> = [];
      let cursor = endKey;
      while (cursor !== startKey) {
        const [c, r] = cursor.split(',').map(Number);
        path.unshift({ col: c, row: r });
        cursor = parent.get(cursor)!;
      }
      return path;
    }
    for (const dir of dirs) {
      const nc = current.col + dir.dc;
      const nr = current.row + dir.dr;
      const nextKey = key(nc, nr);
      if (visited.has(nextKey)) continue;
      if (!isWalkable(nc, nr, tileMap, blockedTiles)) continue;
      visited.add(nextKey);
      parent.set(nextKey, currentKey);
      queue.push({ col: nc, row: nr });
    }
  }
  return [];
}
