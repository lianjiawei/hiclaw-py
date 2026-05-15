import type { FurnitureInstance, OfficeLayout, PlacedFurniture, Seat, TileType as TileTypeVal } from './types.js';
export declare function layoutToTileMap(layout: OfficeLayout): TileTypeVal[][];
export declare function layoutToFurnitureInstances(furniture: PlacedFurniture[]): FurnitureInstance[];
export declare function getBlockedTiles(furniture: PlacedFurniture[], excludeTiles?: Set<string>): Set<string>;
export declare function layoutToSeats(furniture: PlacedFurniture[]): Map<string, Seat>;
export declare function createDefaultLayout(): OfficeLayout;
