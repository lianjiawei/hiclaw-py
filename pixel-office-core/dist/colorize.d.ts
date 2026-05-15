import type { ColorValue, SpriteData } from './types.js';
export declare function getColorizedSprite(cacheKey: string, sprite: SpriteData, color: ColorValue): SpriteData;
export declare function clearColorizeCache(): void;
export declare function adjustSprite(sprite: SpriteData, color: ColorValue): SpriteData;
