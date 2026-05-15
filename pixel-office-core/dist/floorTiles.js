import { CANVAS_ERROR_TILE_COLOR, FALLBACK_FLOOR_COLOR, TILE_SIZE } from './constants.js';
import { clearColorizeCache, getColorizedSprite } from './colorize.js';
const DEFAULT_FLOOR_SPRITE = Array.from({ length: TILE_SIZE }, () => Array(TILE_SIZE).fill(FALLBACK_FLOOR_COLOR));
let floorSprites = [];
export function setFloorSprites(sprites) {
    floorSprites = sprites;
    clearColorizeCache();
}
export function hasFloorSprites() {
    return true;
}
export function getColorizedFloorSprite(patternIndex, color) {
    const key = `floor-${patternIndex}-${color.h}-${color.s}-${color.b}-${color.c}`;
    const base = getFloorSprite(patternIndex);
    if (!base) {
        return Array.from({ length: TILE_SIZE }, () => Array(TILE_SIZE).fill(CANVAS_ERROR_TILE_COLOR));
    }
    return getColorizedSprite(key, base, { ...color, colorize: true });
}
function getFloorSprite(patternIndex) {
    const idx = patternIndex - 1;
    if (idx < 0)
        return null;
    if (idx < floorSprites.length)
        return floorSprites[idx];
    if (floorSprites.length === 0 && patternIndex >= 1)
        return DEFAULT_FLOOR_SPRITE;
    return null;
}
