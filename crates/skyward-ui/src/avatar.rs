//! The picture the home page's device card shows in its circle, where the
//! recovery carries one: the phone's own, read from a PNG.

use crate::canvas::Canvas;
use crate::color::Rgba;
use anyhow::{Context, Result, bail};
use std::path::Path;

/// How wide the picture is kept after it is read: enough for the circle at
/// the densities the pages are drawn at, and small enough to show its whole
/// once for each pixel of the circle.
const KEPT: u32 = 256;

/// A picture taken down to the size of the circle it shows in, its middle
/// square, so that drawing it costs no more than drawing a disc.
#[derive(Clone, Debug)]
pub struct Avatar {
    w: u32,
    h: u32,
    /// Straight-alpha RGBA, row by row.
    px: Vec<u8>,
}

impl Avatar {
    /// The picture in `path`, or why it does not read.
    pub fn load(path: &Path) -> Result<Avatar> {
        let data = std::fs::read(path).with_context(|| format!("read {}", path.display()))?;
        Self::decode(&data).with_context(|| format!("read {}", path.display()))
    }

    /// The picture in `png`: its middle square, averaged down to [`KEPT`] a
    /// side where it is larger; transparency, where it has any, kept.
    pub fn decode(png: &[u8]) -> Result<Avatar> {
        let mut decoder = png::Decoder::new(std::io::Cursor::new(png));
        // A phone's picture may be of any kind, and this reads them all as
        // eight-bit colour with transparency where it has some.
        decoder.set_transformations(png::Transformations::normalize_to_color8());
        let mut reader = decoder.read_info()?;
        let mut buf = vec![0; reader.output_buffer_size()];
        let frame = reader.next_frame(&mut buf)?;
        let (w, h) = (frame.width, frame.height);
        if w == 0 || h == 0 {
            bail!("the picture is empty");
        }
        let channels = match frame.color_type {
            png::ColorType::Rgba => 4,
            png::ColorType::Rgb => 3,
            png::ColorType::GrayscaleAlpha => 2,
            png::ColorType::Grayscale => 1,
            png::ColorType::Indexed => bail!("the picture stays indexed once read"),
        };
        let pixels = &buf[..frame.buffer_size()];
        let at = |x: u32, y: u32| -> (u32, u32, u32, u32) {
            let i = (y * w + x) as usize * channels;
            match channels {
                4 => (
                    pixels[i] as u32,
                    pixels[i + 1] as u32,
                    pixels[i + 2] as u32,
                    pixels[i + 3] as u32,
                ),
                3 => (
                    pixels[i] as u32,
                    pixels[i + 1] as u32,
                    pixels[i + 2] as u32,
                    255,
                ),
                2 => (
                    pixels[i] as u32,
                    pixels[i] as u32,
                    pixels[i] as u32,
                    pixels[i + 1] as u32,
                ),
                _ => (pixels[i] as u32, pixels[i] as u32, pixels[i] as u32, 255),
            }
        };
        // The middle square, then each cell of the kept picture the mean of
        // the picture's own under it: colours averaged by what the pixels
        // cover, so a transparent part does not darken the rest.
        let side = w.min(h);
        let kept = side.min(KEPT);
        let (left, top) = ((w - side) / 2, (h - side) / 2);
        let mut px = vec![0; (kept * kept * 4) as usize];
        for dy in 0..kept {
            let y0 = top + dy * side / kept;
            let y1 = (top + (dy + 1) * side / kept).max(y0 + 1);
            for dx in 0..kept {
                let x0 = left + dx * side / kept;
                let x1 = (left + (dx + 1) * side / kept).max(x0 + 1);
                let (mut a, mut r, mut g, mut b, mut n) = (0u32, 0u32, 0u32, 0u32, 0u32);
                for y in y0..y1 {
                    for x in x0..x1 {
                        let (pr, pg, pb, pa) = at(x, y);
                        a += pa;
                        r += pr * pa;
                        g += pg * pa;
                        b += pb * pa;
                        n += 1;
                    }
                }
                let round = |sum: u32, by: u32| ((sum + by / 2) / by.max(1)) as u8;
                let i = ((dy * kept + dx) * 4) as usize;
                let alpha = (a / n.max(1)) as u8;
                px[i + 3] = alpha;
                if a > 0 {
                    px[i] = round(r, a);
                    px[i + 1] = round(g, a);
                    px[i + 2] = round(b, a);
                }
            }
        }
        Ok(Avatar {
            w: kept,
            h: kept,
            px,
        })
    }

    /// Draw the picture into the disc of radius `r` about (`cx`, `cy`): the
    /// phone's picture is laid over what is there, its corners cut by the
    /// disc's edge as the card's circle cuts them.
    pub fn draw(&self, c: &mut Canvas, cx: f32, cy: f32, r: f32) {
        if r <= 0.0 || self.w == 0 || self.h == 0 {
            return;
        }
        let d = r * 2.0;
        let (left, top) = (cx - r, cy - r);
        let x0 = (left - 1.0).floor() as i32;
        let x1 = (cx + r + 1.0).ceil() as i32;
        let y0 = (top - 1.0).floor() as i32;
        let y1 = (cy + r + 1.0).ceil() as i32;
        for py in y0..y1 {
            let dy = py as f32 + 0.5 - cy;
            for px in x0..x1 {
                let dx = px as f32 + 0.5 - cx;
                let cov = (0.5 - ((dx * dx + dy * dy).sqrt() - r)).clamp(0.0, 1.0);
                if cov <= 0.0 {
                    continue;
                }
                let u =
                    ((px as f32 + 0.5 - left) / d * self.w as f32).clamp(0.0, self.w as f32 - 1.0);
                let v =
                    ((py as f32 + 0.5 - top) / d * self.h as f32).clamp(0.0, self.h as f32 - 1.0);
                c.blend(px, py, self.sample(u, v), cov);
            }
        }
    }

    /// The colour at `u`, `v` of the kept picture, read between its four
    /// nearest pixels.
    fn sample(&self, u: f32, v: f32) -> Rgba {
        let x0 = (u.floor() as u32).min(self.w - 1);
        let y0 = (v.floor() as u32).min(self.h - 1);
        let x1 = (x0 + 1).min(self.w - 1);
        let y1 = (y0 + 1).min(self.h - 1);
        let fx = (u - x0 as f32).clamp(0.0, 1.0);
        let fy = (v - y0 as f32).clamp(0.0, 1.0);
        let texel = |x: u32, y: u32| {
            let i = ((y * self.w + x) * 4) as usize;
            [self.px[i], self.px[i + 1], self.px[i + 2], self.px[i + 3]]
        };
        let (a, b, c, d) = (texel(x0, y0), texel(x1, y0), texel(x0, y1), texel(x1, y1));
        let mix = |at: usize| {
            let top = a[at] as f32 + (b[at] as f32 - a[at] as f32) * fx;
            let bottom = c[at] as f32 + (d[at] as f32 - c[at] as f32) * fx;
            (top + (bottom - top) * fy).round() as u8
        };
        Rgba {
            r: mix(0),
            g: mix(1),
            b: mix(2),
            a: mix(3),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A PNG of the four colours given, row by row.
    fn png(w: u32, h: u32, px: &[[u8; 4]]) -> Vec<u8> {
        let mut out = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut out, w, h);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            let mut writer = encoder.write_header().unwrap();
            writer.write_image_data(px.concat().as_slice()).unwrap();
        }
        out
    }

    #[test]
    fn a_picture_is_kept_as_its_middle_square_and_drawn_inside_the_disc() {
        let red = [255, 0, 0, 255];
        let green = [0, 255, 0, 255];
        let avatar = Avatar::decode(&png(
            4,
            2,
            &[green, red, red, green, green, red, red, green],
        ))
        .unwrap();
        assert_eq!(
            (avatar.w, avatar.h),
            (2, 2),
            "the middle square, two by two"
        );
        let mut c = Canvas::filled(8, 8, Rgba::rgb(255, 255, 255));
        avatar.draw(&mut c, 4.0, 4.0, 3.0);
        let px = |c: &Canvas, x: usize, y: usize| c.data[(y * 8 + x) * 4..(y * 8 + x) * 4 + 4].to_vec();
        assert_eq!(
            px(&c, 0, 0),
            [255, 255, 255, 255],
            "the disc's corners are left as they were"
        );
        assert_eq!(
            px(&c, 4, 4),
            [255, 0, 0, 255],
            "the middle is the picture's own middle"
        );
        let clear = Avatar::decode(&png(1, 1, &[[0, 0, 0, 0]])).unwrap();
        clear.draw(&mut c, 4.0, 4.0, 3.0);
        assert_eq!(
            px(&c, 4, 4),
            [255, 0, 0, 255],
            "a clear picture leaves what is under it"
        );
    }
}
