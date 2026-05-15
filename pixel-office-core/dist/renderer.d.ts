import type { Character, ColorValue, FurnitureInstance, TileType as TileTypeVal } from './types.js';
export declare function renderFrame(ctx: CanvasRenderingContext2D, canvasWidth: number, canvasHeight: number, tileMap: TileTypeVal[][], furniture: FurnitureInstance[], characters: Character[], zoom: number, panX: number, panY: number, tileColors?: Array<ColorValue | null>, cols?: number, rows?: number): {
    offsetX: number;
    offsetY: number;
};
