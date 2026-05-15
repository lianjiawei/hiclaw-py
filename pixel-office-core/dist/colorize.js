const colorizeCache = new Map();
export function getColorizedSprite(cacheKey, sprite, color) {
    const cached = colorizeCache.get(cacheKey);
    if (cached)
        return cached;
    const result = color.colorize ? colorizeSprite(sprite, color) : adjustSprite(sprite, color);
    colorizeCache.set(cacheKey, result);
    return result;
}
export function clearColorizeCache() {
    colorizeCache.clear();
}
function colorizeSprite(sprite, color) {
    const { h, s, b, c } = color;
    return sprite.map((row) => row.map((pixel) => {
        if (!pixel)
            return '';
        const r = parseInt(pixel.slice(1, 3), 16);
        const g = parseInt(pixel.slice(3, 5), 16);
        const bValue = parseInt(pixel.slice(5, 7), 16);
        let lightness = (0.299 * r + 0.587 * g + 0.114 * bValue) / 255;
        if (c !== 0) {
            const factor = (100 + c) / 100;
            lightness = 0.5 + (lightness - 0.5) * factor;
        }
        if (b !== 0) {
            lightness += b / 200;
        }
        lightness = Math.max(0, Math.min(1, lightness));
        const alpha = extractAlpha(pixel);
        return appendAlpha(hslToHex(h, s / 100, lightness), alpha);
    }));
}
export function adjustSprite(sprite, color) {
    const { h: hShift, s: sShift, b, c } = color;
    return sprite.map((row) => row.map((pixel) => {
        if (!pixel)
            return '';
        const r = parseInt(pixel.slice(1, 3), 16);
        const g = parseInt(pixel.slice(3, 5), 16);
        const bValue = parseInt(pixel.slice(5, 7), 16);
        const alpha = extractAlpha(pixel);
        const [origH, origS, origL] = rgbToHsl(r, g, bValue);
        const newH = (((origH + hShift) % 360) + 360) % 360;
        const newS = Math.max(0, Math.min(1, origS + sShift / 100));
        let lightness = origL;
        if (c !== 0) {
            const factor = (100 + c) / 100;
            lightness = 0.5 + (lightness - 0.5) * factor;
        }
        if (b !== 0) {
            lightness += b / 200;
        }
        lightness = Math.max(0, Math.min(1, lightness));
        return appendAlpha(hslToHex(newH, newS, lightness), alpha);
    }));
}
function extractAlpha(pixel) {
    return pixel.length > 7 ? parseInt(pixel.slice(7, 9), 16) : 255;
}
function appendAlpha(hex, alpha) {
    if (alpha >= 255)
        return hex;
    return `${hex}${alpha.toString(16).padStart(2, '0').toUpperCase()}`;
}
function hslToHex(h, s, l) {
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const hp = h / 60;
    const x = c * (1 - Math.abs((hp % 2) - 1));
    let r1 = 0;
    let g1 = 0;
    let b1 = 0;
    if (hp < 1) {
        r1 = c;
        g1 = x;
    }
    else if (hp < 2) {
        r1 = x;
        g1 = c;
    }
    else if (hp < 3) {
        g1 = c;
        b1 = x;
    }
    else if (hp < 4) {
        g1 = x;
        b1 = c;
    }
    else if (hp < 5) {
        r1 = x;
        b1 = c;
    }
    else {
        r1 = c;
        b1 = x;
    }
    const m = l - c / 2;
    const r = clamp255(Math.round((r1 + m) * 255));
    const g = clamp255(Math.round((g1 + m) * 255));
    const bOut = clamp255(Math.round((b1 + m) * 255));
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bOut.toString(16).padStart(2, '0')}`.toUpperCase();
}
function rgbToHsl(r, g, b) {
    const rf = r / 255;
    const gf = g / 255;
    const bf = b / 255;
    const max = Math.max(rf, gf, bf);
    const min = Math.min(rf, gf, bf);
    const l = (max + min) / 2;
    if (max === min)
        return [0, 0, l];
    const d = max - min;
    const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    let h = 0;
    if (max === rf)
        h = ((gf - bf) / d + (gf < bf ? 6 : 0)) * 60;
    else if (max === gf)
        h = ((bf - rf) / d + 2) * 60;
    else
        h = ((rf - gf) / d + 4) * 60;
    return [h, s, l];
}
function clamp255(v) {
    return Math.max(0, Math.min(255, v));
}
