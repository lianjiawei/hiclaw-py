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
      continue;
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
  const width = Math.round(96 * Math.max(zoom / 2, 1));
  const height = Math.round((ch.statusDetail ? 34 : 22) * Math.max(zoom / 2, 1));
  const x = Math.round(centerX - width / 2);
  const y = Math.round(anchorY - height - 6 * zoom);
  const tail = Math.max(4, Math.round(3 * zoom));
  const padding = Math.max(6, Math.round(4 * zoom));

  ctx.save();
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(x, y, width, height);
  ctx.fillRect(centerX - tail, y + height, tail * 2, tail);
  ctx.fillStyle = '#eef2fb';
  ctx.fillRect(x + 3, y + 3, width - 6, height - 6);
  ctx.fillStyle = '#1f2b45';
  ctx.font = `${Math.max(10, Math.round(6 * zoom))}px monospace`;
  ctx.textBaseline = 'top';
  drawClippedText(ctx, ch.statusText || '', x + padding, y + padding, width - padding * 2);
  if (ch.statusDetail) {
    ctx.fillStyle = '#61708f';
    ctx.font = `${Math.max(9, Math.round(5 * zoom))}px monospace`;
    drawClippedText(ctx, ch.statusDetail, x + padding, y + padding + Math.round(11 * Math.max(zoom / 2, 1)), width - padding * 2);
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
