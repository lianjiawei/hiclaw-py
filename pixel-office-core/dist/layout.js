import { DEFAULT_COLS, DEFAULT_ROWS, TILE_SIZE } from './constants.js';
import { getColorizedSprite } from './colorize.js';
import { getCatalogEntry } from './furnitureCatalog.js';
import { TileType } from './types.js';
export function layoutToTileMap(layout) {
    const map = [];
    for (let r = 0; r < layout.rows; r++) {
        const row = [];
        for (let c = 0; c < layout.cols; c++) {
            row.push(layout.tiles[r * layout.cols + c]);
        }
        map.push(row);
    }
    return map;
}
export function layoutToFurnitureInstances(furniture) {
    const deskZByTile = new Map();
    for (const item of furniture) {
        const entry = getCatalogEntry(item.type);
        if (!entry || !entry.isDesk)
            continue;
        const deskZY = item.row * TILE_SIZE + entry.sprite.length;
        for (let dr = 0; dr < entry.footprintH; dr++) {
            for (let dc = 0; dc < entry.footprintW; dc++) {
                const key = `${item.col + dc},${item.row + dr}`;
                const prev = deskZByTile.get(key);
                if (prev === undefined || deskZY > prev)
                    deskZByTile.set(key, deskZY);
            }
        }
    }
    const instances = [];
    for (const item of furniture) {
        const entry = getCatalogEntry(item.type);
        if (!entry)
            continue;
        const x = item.col * TILE_SIZE;
        const y = item.row * TILE_SIZE;
        let zY = y + entry.sprite.length;
        if (entry.category === 'wall' || entry.canPlaceOnWalls) {
            zY += 0.25;
        }
        if (entry.category === 'chairs') {
            zY = entry.orientation === 'back' ? (item.row + entry.footprintH) * TILE_SIZE + 1 : (item.row + 1) * TILE_SIZE;
        }
        if (entry.canPlaceOnSurfaces) {
            for (let dr = 0; dr < entry.footprintH; dr++) {
                for (let dc = 0; dc < entry.footprintW; dc++) {
                    const deskZ = deskZByTile.get(`${item.col + dc},${item.row + dr}`);
                    if (deskZ !== undefined && deskZ + 0.5 > zY)
                        zY = deskZ + 0.5;
                }
            }
        }
        let sprite = entry.sprite;
        if (item.color) {
            const { h, s, b, c } = item.color;
            sprite = getColorizedSprite(`furn-${item.type}-${h}-${s}-${b}-${c}-${item.color.colorize ? 1 : 0}`, entry.sprite, item.color);
        }
        const mirrored = !!entry.mirrorSide && item.type.endsWith(':left');
        instances.push({ sprite, x, y, zY, mirrored: mirrored || undefined });
    }
    return instances;
}
export function getBlockedTiles(furniture, excludeTiles) {
    const tiles = new Set();
    for (const item of furniture) {
        const entry = getCatalogEntry(item.type);
        if (!entry)
            continue;
        const bgRows = entry.backgroundTiles || 0;
        for (let dr = 0; dr < entry.footprintH; dr++) {
            if (dr < bgRows)
                continue;
            for (let dc = 0; dc < entry.footprintW; dc++) {
                const key = `${item.col + dc},${item.row + dr}`;
                if (!excludeTiles || !excludeTiles.has(key))
                    tiles.add(key);
            }
        }
    }
    return tiles;
}
export function layoutToSeats(furniture) {
    const seats = new Map();
    const deskTiles = new Set();
    for (const item of furniture) {
        const entry = getCatalogEntry(item.type);
        if (!entry || !entry.isDesk)
            continue;
        for (let dr = 0; dr < entry.footprintH; dr++) {
            for (let dc = 0; dc < entry.footprintW; dc++) {
                deskTiles.add(`${item.col + dc},${item.row + dr}`);
            }
        }
    }
    const dirs = [
        { dc: 0, dr: -1, facing: 3 },
        { dc: 0, dr: 1, facing: 0 },
        { dc: -1, dr: 0, facing: 1 },
        { dc: 1, dr: 0, facing: 2 },
    ];
    for (const item of furniture) {
        const entry = getCatalogEntry(item.type);
        if (!entry || entry.category !== 'chairs')
            continue;
        let seatCount = 0;
        const bgRows = entry.backgroundTiles ?? 0;
        for (let dr = bgRows; dr < entry.footprintH; dr++) {
            for (let dc = 0; dc < entry.footprintW; dc++) {
                const tileCol = item.col + dc;
                const tileRow = item.row + dr;
                let facingDir = 0;
                if (entry.orientation) {
                    facingDir = orientationToFacing(entry.orientation);
                }
                else {
                    for (const dir of dirs) {
                        if (deskTiles.has(`${tileCol + dir.dc},${tileRow + dir.dr}`)) {
                            facingDir = dir.facing;
                            break;
                        }
                    }
                }
                const seatUid = seatCount === 0 ? item.uid : `${item.uid}:${seatCount}`;
                seats.set(seatUid, { uid: seatUid, seatCol: tileCol, seatRow: tileRow, facingDir, assigned: false });
                seatCount++;
            }
        }
    }
    return seats;
}
export function createDefaultLayout() {
    const tiles = [];
    const tileColors = [];
    for (let r = 0; r < DEFAULT_ROWS; r++) {
        for (let c = 0; c < DEFAULT_COLS; c++) {
            if (r === 0 || r === DEFAULT_ROWS - 1 || c === 0 || c === DEFAULT_COLS - 1) {
                tiles.push(TileType.WALL);
                tileColors.push(null);
            }
            else {
                tiles.push(c < 10 ? TileType.FLOOR_1 : TileType.FLOOR_2);
                tileColors.push(c < 10 ? { h: 35, s: 30, b: 15, c: 0 } : { h: 25, s: 45, b: 5, c: 10 });
            }
        }
    }
    return { version: 1, cols: DEFAULT_COLS, rows: DEFAULT_ROWS, tiles, tileColors, furniture: [] };
}
function orientationToFacing(orientation) {
    switch (orientation) {
        case 'front':
            return 0;
        case 'back':
            return 3;
        case 'left':
            return 1;
        case 'right':
        case 'side':
            return 2;
        default:
            return 0;
    }
}
