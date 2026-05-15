import { CHARACTER_SITTING_OFFSET_PX, CHARACTER_Z_SORT_OFFSET, FALLBACK_FLOOR_COLOR, TILE_SIZE, WALL_COLOR } from './constants.js';
import { getColorizedFloorSprite, hasFloorSprites } from './floorTiles.js';
import { getCachedSprite } from './spriteCache.js';
import { getCharacterSprites } from './spriteData.js';
import type { Character, ColorValue, FurnitureInstance, SpriteData, TileType as TileTypeVal } from './types.js';
import { CharacterState, TileType } from './types.js';
import { getWallInstances, hasWallSprites, wallColorToHex } from './wallTiles.js';
import { BUBBLE_PERMISSION_SPRITE, BUBBLE_WAITING_SPRITE } from './bubbleData.js';
import { getCharacterSprite } from './characters.js';

interface ZDrawable {
  zY: number;
  draw: (ctx: CanvasRenderingContext2D) => void;
}

function normalizeBubbleText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function getBubbleTone(ch: Character): { accent: string; shadow: string } {
  if (ch.bubbleType === 'permission') return { accent: '#cca700', shadow: 'rgba(204, 167, 0, 0.2)' };
  if (ch.bubbleType === 'waiting') return { accent: '#44bb66', shadow: 'rgba(68, 187, 102, 0.18)' };
  if (ch.statusText?.includes('完成')) return { accent: '#44bb66', shadow: 'rgba(68, 187, 102, 0.16)' };
  if (ch.currentTool) return { accent: '#7c9bff', shadow: 'rgba(124, 155, 255, 0.16)' };
  return { accent: '#9aa7b9', shadow: 'rgba(154, 167, 185, 0.14)' };
}

function drawScrollingText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, speed = 1): void {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!normalized) return;
  const textWidth = ctx.measureText(normalized).width;
  if (textWidth <= maxWidth) {
    ctx.fillText(normalized, x, y);
    return;
  }
  const gap = 24;
  const cycle = textWidth + gap;
  const elapsed = performance.now() / 1000;
  const shift = (elapsed * 18 * speed) % cycle;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y - 1, maxWidth, Math.max(12, Number.parseInt(ctx.font, 10) + 4));
  ctx.clip();
  ctx.fillText(normalized, x - shift, y);
  ctx.fillText(normalized, x - shift + cycle, y);
  ctx.restore();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  tileMap: TileTypeVal[][],
  furniture: FurnitureInstance[],
  characters: Character[],
  zoom: number,
  panX: number,
  panY: number,
  tileColors?: Array<ColorValue | null>,
  cols?: number,
  rows?: number,
): { offsetX: number; offsetY: number } {
  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  const mapCols = cols ?? (tileMap[0]?.length ?? 0);
  const mapRows = rows ?? tileMap.length;
  const mapWidth = mapCols * TILE_SIZE * zoom;
  const mapHeight = mapRows * TILE_SIZE * zoom;
  const offsetX = Math.round((canvasWidth - mapWidth) / 2 + panX);
  const offsetY = Math.round((canvasHeight - mapHeight) / 2 + panY);
  renderTileGrid(ctx, tileMap, offsetX, offsetY, zoom, tileColors, mapCols);
  const allFurniture = hasWallSprites() ? [...furniture, ...getWallInstances(tileMap, tileColors, mapCols)] : furniture;
  renderScene(ctx, allFurniture, characters, offsetX, offsetY, zoom);
  renderBubbles(ctx, characters, offsetX, offsetY, zoom);
  return { offsetX, offsetY };
}

function renderTileGrid(ctx: CanvasRenderingContext2D, tileMap: TileTypeVal[][], offsetX: number, offsetY: number, zoom: number, tileColors?: Array<ColorValue | null>, cols?: number): void {
  const s = TILE_SIZE * zoom;
  const useSpriteFloors = hasFloorSprites();
  const tmRows = tileMap.length;
  const tmCols = tmRows > 0 ? tileMap[0].length : 0;
  const layoutCols = cols ?? tmCols;
  for (let r = 0; r < tmRows; r++) {
    for (let c = 0; c < tmCols; c++) {
      const tile = tileMap[r][c];
      if (tile === TileType.VOID) continue;
      if (tile === TileType.WALL || !useSpriteFloors) {
        if (tile === TileType.WALL) {
          const wallColor = tileColors?.[r * layoutCols + c];
          ctx.fillStyle = wallColor ? wallColorToHex(wallColor) : WALL_COLOR;
        } else {
          ctx.fillStyle = FALLBACK_FLOOR_COLOR;
        }
        ctx.fillRect(offsetX + c * s, offsetY + r * s, s, s);
        continue;
      }
      const color = tileColors?.[r * layoutCols + c] ?? { h: 0, s: 0, b: 0, c: 0 };
      const sprite = getColorizedFloorSprite(tile, color);
      const cached = getCachedSprite(sprite, zoom);
      ctx.drawImage(cached, offsetX + c * s, offsetY + r * s);
    }
  }
}

function renderScene(ctx: CanvasRenderingContext2D, furniture: FurnitureInstance[], characters: Character[], offsetX: number, offsetY: number, zoom: number): void {
  const drawables: ZDrawable[] = [];
  for (const item of furniture) {
    const cached = getCachedSprite(item.sprite, zoom);
    const fx = offsetX + item.x * zoom;
    const fy = offsetY + item.y * zoom;
    if (item.mirrored) {
      drawables.push({
        zY: item.zY,
        draw: (canvasCtx) => {
          canvasCtx.save();
          canvasCtx.translate(fx + cached.width, fy);
          canvasCtx.scale(-1, 1);
          canvasCtx.drawImage(cached, 0, 0);
          canvasCtx.restore();
        },
      });
    } else {
      drawables.push({ zY: item.zY, draw: (canvasCtx) => canvasCtx.drawImage(cached, fx, fy) });
    }
  }
  for (const ch of characters) {
    const sprites = getCharacterSprites(ch.palette, ch.hueShift);
    const spriteData = getCharacterSprite(ch, sprites);
    const cached = getCachedSprite(spriteData, zoom);
    const sittingOffset = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0;
    const drawX = Math.round(offsetX + ch.x * zoom - cached.width / 2);
    const drawY = Math.round(offsetY + (ch.y + sittingOffset) * zoom - cached.height);
    const zY = ch.y + TILE_SIZE / 2 + CHARACTER_Z_SORT_OFFSET;
    drawables.push({ zY, draw: (canvasCtx) => canvasCtx.drawImage(cached, drawX, drawY) });
  }
  drawables.sort((a, b) => a.zY - b.zY);
  for (const drawable of drawables) drawable.draw(ctx);
}

const BUBBLE_VERTICAL_OFFSET_PX = 24;
const BUBBLE_FADE_DURATION_SEC = 0.5;

function renderBubbles(ctx: CanvasRenderingContext2D, characters: Character[], offsetX: number, offsetY: number, zoom: number): void {
  for (const ch of characters) {
    if (!ch.bubbleType && !ch.statusText && !ch.statusDetail) continue;
    if (ch.statusText || ch.statusDetail) {
      renderStatusBubble(ctx, ch, offsetX, offsetY, zoom);
      if (!ch.bubbleType) continue;
    }
    const sprite = ch.bubbleType === 'permission' ? BUBBLE_PERMISSION_SPRITE : BUBBLE_WAITING_SPRITE;
    let alpha = 1.0;
    if (ch.bubbleType === 'waiting' && ch.bubbleTimer < BUBBLE_FADE_DURATION_SEC) {
      alpha = ch.bubbleTimer / BUBBLE_FADE_DURATION_SEC;
    }
    const cached = getCachedSprite(sprite, zoom);
    const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0;
    const bubbleX = Math.round(offsetX + ch.x * zoom - cached.width / 2);
    const bubbleY = Math.round(offsetY + (ch.y + sittingOff - BUBBLE_VERTICAL_OFFSET_PX) * zoom - cached.height);
    ctx.save();
    if (alpha < 1.0) ctx.globalAlpha = alpha;
    ctx.drawImage(cached, bubbleX, bubbleY);
    ctx.restore();
  }
}

function renderStatusBubble(ctx: CanvasRenderingContext2D, ch: Character, offsetX: number, offsetY: number, zoom: number): void {
  const sittingOff = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0;
  const centerX = Math.round(offsetX + ch.x * zoom);
  const anchorY = Math.round(offsetY + (ch.y + sittingOff - BUBBLE_VERTICAL_OFFSET_PX) * zoom);
  const scale = Math.max(zoom / 2, 1);
  const detail = normalizeBubbleText(ch.statusDetail || '');
  const title = normalizeBubbleText(ch.statusText || detail);
  const detailLine = ch.statusText ? detail : '';
  const padding = Math.round(5 * scale);
  const titleFont = Math.max(10, Math.round(6 * zoom));
  const detailFont = Math.max(9, Math.round(5 * zoom));

  ctx.save();
  ctx.font = `${titleFont}px monospace`;
  const titleWidth = ctx.measureText(title).width;
  ctx.font = `${detailFont}px monospace`;
  const detailWidth = detailLine ? ctx.measureText(detailLine).width : 0;
  const measuredWidth = Math.max(titleWidth, detailWidth) + padding * 2 + Math.round(9 * scale);
  const width = Math.round(clamp(measuredWidth, 88 * scale, 132 * scale));
  const height = Math.round((detailLine ? 36 : 24) * scale);
  const x = Math.round(centerX - width / 2);
  const y = Math.round(anchorY - height - 6 * zoom);
  const tail = Math.max(4, Math.round(3 * zoom));
  const tone = getBubbleTone(ch);

  ctx.fillStyle = tone.shadow;
  ctx.fillRect(x + Math.round(2 * scale), y + Math.round(2 * scale), width, height);
  ctx.fillStyle = '#555566';
  ctx.fillRect(x, y, width, height);
  ctx.fillRect(centerX - tail, y + height, tail * 2, tail);
  ctx.fillStyle = '#f7f8ff';
  ctx.fillRect(x + 2, y + 2, width - 4, height - 4);
  ctx.fillStyle = '#eef2fb';
  ctx.fillRect(x + 4, y + 4, width - 8, height - 8);
  ctx.fillStyle = tone.accent;
  ctx.fillRect(x + 4, y + 4, Math.max(3, Math.round(3 * scale)), height - 8);

  ctx.fillStyle = '#1f2b45';
  ctx.textBaseline = 'top';
  ctx.font = `${titleFont}px monospace`;
  drawScrollingText(ctx, title, x + padding + Math.round(3 * scale), y + padding, width - padding * 2 - Math.round(3 * scale));
  if (detailLine) {
    ctx.fillStyle = '#61708f';
    ctx.font = `${detailFont}px monospace`;
    drawScrollingText(
      ctx,
      detailLine,
      x + padding + Math.round(3 * scale),
      y + padding + Math.round(11 * scale),
      width - padding * 2 - Math.round(3 * scale),
      0.62,
    );
  }
  ctx.restore();
}

function drawClippedText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number): void {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!normalized) return;
  let value = normalized;
  while (value.length > 1 && ctx.measureText(value).width > maxWidth) {
    value = value.slice(0, -2);
  }
  if (value.length < normalized.length) value = `${value}…`;
  ctx.fillText(value, x, y);
}
