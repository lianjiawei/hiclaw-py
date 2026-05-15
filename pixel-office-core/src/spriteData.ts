import { CHAR_FRAME_H, CHAR_FRAME_W, CHAR_FRAMES_PER_ROW } from './constants.js';
import { adjustSprite } from './colorize.js';
import type { CharacterDirectionSprites, CharacterSprites, ColorValue, Direction, SpriteData } from './types.js';
import { Direction as Dir } from './types.js';

let loadedCharacters: CharacterDirectionSprites[] | null = null;
const spriteCache = new Map<string, CharacterSprites>();

export function setCharacterTemplates(data: CharacterDirectionSprites[]): void {
  loadedCharacters = data;
  spriteCache.clear();
}

export function getLoadedCharacterCount(): number {
  return loadedCharacters?.length ?? 0;
}

export function getCharacterSprites(paletteIndex: number, hueShift = 0): CharacterSprites {
  const cacheKey = `${paletteIndex}:${hueShift}`;
  const cached = spriteCache.get(cacheKey);
  if (cached) return cached;

  let sprites: CharacterSprites;
  if (loadedCharacters && loadedCharacters.length > 0) {
    const char = loadedCharacters[paletteIndex % loadedCharacters.length];
    const d = char.down;
    const u = char.up;
    const rt = char.right;
    const flip = flipSpriteHorizontal;
    sprites = {
      walk: {
        [Dir.DOWN]: [d[0], d[1], d[2], d[1]],
        [Dir.UP]: [u[0], u[1], u[2], u[1]],
        [Dir.RIGHT]: [rt[0], rt[1], rt[2], rt[1]],
        [Dir.LEFT]: [flip(rt[0]), flip(rt[1]), flip(rt[2]), flip(rt[1])],
      } as Record<Direction, [SpriteData, SpriteData, SpriteData, SpriteData]>,
      typing: {
        [Dir.DOWN]: [d[3], d[4]],
        [Dir.UP]: [u[3], u[4]],
        [Dir.RIGHT]: [rt[3], rt[4]],
        [Dir.LEFT]: [flip(rt[3]), flip(rt[4])],
      } as Record<Direction, [SpriteData, SpriteData]>,
      reading: {
        [Dir.DOWN]: [d[5], d[6]],
        [Dir.UP]: [u[5], u[6]],
        [Dir.RIGHT]: [rt[5], rt[6]],
        [Dir.LEFT]: [flip(rt[5]), flip(rt[6])],
      } as Record<Direction, [SpriteData, SpriteData]>,
    };
  } else {
    const empty = emptySprite(CHAR_FRAME_W, CHAR_FRAME_H);
    const walkSet: [SpriteData, SpriteData, SpriteData, SpriteData] = [empty, empty, empty, empty];
    const pairSet: [SpriteData, SpriteData] = [empty, empty];
    sprites = {
      walk: {
        [Dir.DOWN]: walkSet,
        [Dir.UP]: walkSet,
        [Dir.RIGHT]: walkSet,
        [Dir.LEFT]: walkSet,
      } as Record<Direction, [SpriteData, SpriteData, SpriteData, SpriteData]>,
      typing: {
        [Dir.DOWN]: pairSet,
        [Dir.UP]: pairSet,
        [Dir.RIGHT]: pairSet,
        [Dir.LEFT]: pairSet,
      } as Record<Direction, [SpriteData, SpriteData]>,
      reading: {
        [Dir.DOWN]: pairSet,
        [Dir.UP]: pairSet,
        [Dir.RIGHT]: pairSet,
        [Dir.LEFT]: pairSet,
      } as Record<Direction, [SpriteData, SpriteData]>,
    };
  }

  if (hueShift !== 0) {
    sprites = hueShiftSprites(sprites, hueShift);
  }
  spriteCache.set(cacheKey, sprites);
  return sprites;
}

function hueShiftSprites(sprites: CharacterSprites, hueShift: number): CharacterSprites {
  const color: ColorValue = { h: hueShift, s: 0, b: 0, c: 0 };
  const shift = (sprite: SpriteData) => adjustSprite(sprite, color);
  const shiftWalk = (arr: [SpriteData, SpriteData, SpriteData, SpriteData]) => [shift(arr[0]), shift(arr[1]), shift(arr[2]), shift(arr[3])] as [SpriteData, SpriteData, SpriteData, SpriteData];
  const shiftPair = (arr: [SpriteData, SpriteData]) => [shift(arr[0]), shift(arr[1])] as [SpriteData, SpriteData];
  return {
    walk: {
      [Dir.DOWN]: shiftWalk(sprites.walk[Dir.DOWN]),
      [Dir.UP]: shiftWalk(sprites.walk[Dir.UP]),
      [Dir.RIGHT]: shiftWalk(sprites.walk[Dir.RIGHT]),
      [Dir.LEFT]: shiftWalk(sprites.walk[Dir.LEFT]),
    } as Record<Direction, [SpriteData, SpriteData, SpriteData, SpriteData]>,
    typing: {
      [Dir.DOWN]: shiftPair(sprites.typing[Dir.DOWN]),
      [Dir.UP]: shiftPair(sprites.typing[Dir.UP]),
      [Dir.RIGHT]: shiftPair(sprites.typing[Dir.RIGHT]),
      [Dir.LEFT]: shiftPair(sprites.typing[Dir.LEFT]),
    } as Record<Direction, [SpriteData, SpriteData]>,
    reading: {
      [Dir.DOWN]: shiftPair(sprites.reading[Dir.DOWN]),
      [Dir.UP]: shiftPair(sprites.reading[Dir.UP]),
      [Dir.RIGHT]: shiftPair(sprites.reading[Dir.RIGHT]),
      [Dir.LEFT]: shiftPair(sprites.reading[Dir.LEFT]),
    } as Record<Direction, [SpriteData, SpriteData]>,
  };
}

function flipSpriteHorizontal(sprite: SpriteData): SpriteData {
  return sprite.map((row) => [...row].reverse());
}

function emptySprite(w: number, h: number): SpriteData {
  return Array.from({ length: h }, () => new Array(w).fill(''));
}

export function decodeCharacterImage(image: HTMLImageElement): CharacterDirectionSprites {
  const down: SpriteData[] = [];
  const up: SpriteData[] = [];
  const right: SpriteData[] = [];
  const rows = [down, up, right];
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(image, 0, 0);
  for (let dirIndex = 0; dirIndex < rows.length; dirIndex++) {
    for (let frame = 0; frame < CHAR_FRAMES_PER_ROW; frame++) {
      rows[dirIndex].push(readSprite(ctx, frame * CHAR_FRAME_W, dirIndex * CHAR_FRAME_H, CHAR_FRAME_W, CHAR_FRAME_H));
    }
  }
  return { down, up, right };
}

function readSprite(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number): SpriteData {
  const imageData = ctx.getImageData(x, y, width, height).data;
  const sprite: SpriteData = [];
  for (let row = 0; row < height; row++) {
    const line: string[] = [];
    for (let col = 0; col < width; col++) {
      const idx = (row * width + col) * 4;
      const a = imageData[idx + 3];
      if (a < 2) {
        line.push('');
        continue;
      }
      const r = imageData[idx];
      const g = imageData[idx + 1];
      const b = imageData[idx + 2];
      const base = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toUpperCase();
      line.push(a >= 255 ? base : `${base}${a.toString(16).padStart(2, '0').toUpperCase()}`);
    }
    sprite.push(line);
  }
  return sprite;
}
