import type { ColorValue, FurnitureInstance, SpriteData, TileType as TileTypeVal } from './types.js';
export declare function setWallSprites(sets: SpriteData[][]): void;
export declare function hasWallSprites(): boolean;
export declare function getWallInstances(tileMap: TileTypeVal[][], tileColors?: Array<ColorValue | null>, cols?: number): FurnitureInstance[];
export declare function wallColorToHex(color: ColorValue): string;
