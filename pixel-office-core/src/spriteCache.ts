import type { SpriteData } from './types.js';

const outlineCache = new Map<SpriteData, SpriteData>();
const cache = new Map<string, HTMLCanvasElement>();

export function getOutlineSprite(sprite: SpriteData): SpriteData {
  const cached = outlineCache.get(sprite);
  if (cached) return cached;
  const rows = sprite.length;
  const cols = rows > 0 ? sprite[0].length : 0;
  const outline: SpriteData = Array.from({ length: rows + 2 }, () => Array(cols + 2).fill(''));
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (!sprite[r][c]) continue;
      for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
          if (outline[r + dr + 1][c + dc + 1] === '') {
            outline[r + dr + 1][c + dc + 1] = '#FFFFFF';
          }
        }
      }
    }
  }
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (sprite[r][c]) outline[r + 1][c + 1] = '';
    }
  }
  outlineCache.set(sprite, outline);
  return outline;
}

export function getCachedSprite(sprite: SpriteData, zoom: number): HTMLCanvasElement {
  const key = `${zoom}:${spriteKey(sprite)}`;
  const cached = cache.get(key);
  if (cached) return cached;
  const rows = sprite.length;
  const cols = rows > 0 ? sprite[0].length : 0;
  const canvas = document.createElement('canvas');
  canvas.width = cols * zoom;
  canvas.height = rows * zoom;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const color = sprite[r][c];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(c * zoom, r * zoom, zoom, zoom);
    }
  }
  cache.set(key, canvas);
  return canvas;
}

function spriteKey(sprite: SpriteData): string {
  return sprite.map((row) => row.join(',')).join('|');
}
