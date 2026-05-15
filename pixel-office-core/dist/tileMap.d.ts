import type { TileType } from './types.js';
export declare function isWalkable(col: number, row: number, tileMap: TileType[][], blockedTiles: Set<string>): boolean;
export declare function getWalkableTiles(tileMap: TileType[][], blockedTiles: Set<string>): Array<{
    col: number;
    row: number;
}>;
export declare function findPath(startCol: number, startRow: number, endCol: number, endRow: number, tileMap: TileType[][], blockedTiles: Set<string>): Array<{
    col: number;
    row: number;
}>;
