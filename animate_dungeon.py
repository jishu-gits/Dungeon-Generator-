"""
animate_dungeon.py

Standalone script that loads stage1.png..stage4.png and writes:
  - dungeon_evolution.gif
  - dungeon_evolution.mp4

Design:
  - Modular functions for loading images and writing GIF/MP4.
  - Primary writers use imageio; an optional Matplotlib.FuncAnimation writer is provided
    for environments where ffmpeg is configured for Matplotlib.

Usage:
  python animate_dungeon.py
"""
from typing import List, Sequence, Optional
from pathlib import Path
import sys

# Prefer imageio for simple read/write
try:
    import imageio.v2 as imageio
    _HAS_IMAGEIO = True
except Exception:
    _HAS_IMAGEIO = False

# Matplotlib only required for optional animation writer and preview
try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False

# Pillow fallback for image loading if imageio missing
try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


def load_stage_images(paths: Sequence[Path]) -> List:
    """
    Load images from disk in the order provided.
    Returns list of numpy arrays (H,W,3) uint8.
    """
    imgs = []
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"Stage image not found: {p}")
        if _HAS_IMAGEIO:
            img = imageio.imread(str(p))
            # Ensure RGB (drop alpha if present)
            if img.ndim == 2:
                # grayscale -> convert to RGB
                import numpy as np
                img = np.stack([img] * 3, axis=-1)
            elif img.shape[2] == 4:
                img = img[:, :, :3]
        elif _HAS_PIL:
            img = Image.open(p).convert("RGB")
            import numpy as np
            img = np.array(img)
        else:
            raise RuntimeError("No image loader available (install imageio or pillow).")
        imgs.append(img)
    return imgs


def ensure_even_dimensions(img):
    """
    Ensure both width and height are even. If either dimension is odd,
    resize down by 1 pixel (crop the last row/column) so both are divisible by 2.

    Accepts a numpy array image (H, W, ...) and returns a numpy array.
    """
    # Import numpy locally to avoid hard dependency at module import time
    try:
        import numpy as np
    except Exception:
        raise RuntimeError("numpy is required for ensure_even_dimensions()")

    if not hasattr(img, "shape"):
        raise TypeError("ensure_even_dimensions expects an array-like with .shape")

    h, w = img.shape[0], img.shape[1]
    new_h = h - (h % 2)
    new_w = w - (w % 2)
    if new_h == h and new_w == w:
        return img
    # Crop without copying more than necessary
    if img.ndim == 2:
        return img[:new_h, :new_w]
    else:
        return img[:new_h, :new_w, ...]


def save_gif(images: List, out_path: Path, duration: float = 0.8) -> None:
    """
    Write animated GIF from images.
    duration: seconds per frame.
    """
    if not _HAS_IMAGEIO:
        raise RuntimeError("imageio required to write GIF (install imageio).")
    # imageio expects list of arrays
    imageio.mimsave(str(out_path), images, duration=duration)
    print(f"Saved GIF: {out_path}")


def save_mp4_imageio(images: List, out_path: Path, fps: int = 2) -> None:
    """
    Write MP4 using imageio (requires ffmpeg available to imageio).
    """
    if not _HAS_IMAGEIO:
        raise RuntimeError("imageio required to write MP4 (install imageio).")
    # imageio will select ffmpeg writer automatically by file extension
    try:
        imageio.mimwrite(str(out_path), images, fps=fps, macro_block_size=None)
        print(f"Saved MP4 via imageio: {out_path}")
    except Exception as e:
        raise RuntimeError(f"imageio failed to write MP4: {e}")


def save_mp4_matplotlib(images: List, out_path: Path, fps: int = 2) -> None:
    """
    Optional: Use matplotlib.animation.FuncAnimation + ffmpeg writer.
    This requires Matplotlib configured with ffmpeg.
    """
    if not _HAS_MPL:
        raise RuntimeError("matplotlib required for this writer (install matplotlib).")

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axis("off")
    im = ax.imshow(images[0], animated=True, interpolation="nearest")

    def _update(i):
        im.set_array(images[i])
        return (im,)

    ani = animation.FuncAnimation(fig, _update, frames=len(images), interval=1000 // fps, blit=True)
    # Try saving with ffmpeg writer
    try:
        Writer = animation.writers['ffmpeg']
        writer = Writer(fps=fps, metadata=dict(artist='animate_dungeon'), bitrate=2000)
        ani.save(str(out_path), writer=writer)
        print(f"Saved MP4 via matplotlib+ffmpeg: {out_path}")
    finally:
        plt.close(fig)


def build_default_stage_paths(base_dir: Optional[Path] = None) -> List[Path]:
    if base_dir is None:
        base_dir = Path.cwd()
    return [base_dir / f"stage{i}.png" for i in (1, 2, 3, 4)]


def main(output_gif: str = "dungeon_evolution.gif", output_mp4: str = "dungeon_evolution.mp4"):
    base = Path.cwd()
    paths = build_default_stage_paths(base)
    try:
        imgs = load_stage_images(paths)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Ensure visualize_dungeon.py was run and produced stage1.png..stage4.png in this directory.", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR loading images: {e}", file=sys.stderr)
        sys.exit(3)

    out_gif = base / output_gif
    out_mp4 = base / output_mp4

    # Write GIF (unchanged behavior)
    try:
        save_gif(imgs, out_gif, duration=0.9)
    except Exception as e:
        print(f"Failed to write GIF: {e}", file=sys.stderr)

    # Prepare frames with even dimensions for MP4 writers
    try:
        even_imgs = [ensure_even_dimensions(img) for img in imgs]
    except Exception as e:
        print(f"Failed to normalize frame dimensions for MP4: {e}", file=sys.stderr)
        even_imgs = imgs  # fallback to original frames

    # Prefer imageio MP4 for portability; fallback to matplotlib writer if available
    mp4_written = False
    try:
        save_mp4_imageio(even_imgs, out_mp4, fps=2)
        mp4_written = True
    except Exception as e:
        print(f"imageio MP4 write failed: {e}", file=sys.stderr)
        if _HAS_MPL:
            try:
                save_mp4_matplotlib(even_imgs, out_mp4, fps=2)
                mp4_written = True
            except Exception as e2:
                print(f"matplotlib MP4 write failed: {e2}", file=sys.stderr)

    if not mp4_written:
        # Clear, user-facing message but do not exit with error
        print("MP4 export failed, GIF saved successfully.", file=sys.stderr)


if __name__ == "__main__":
    main()
