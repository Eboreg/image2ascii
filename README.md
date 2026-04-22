# image2ascii-core

<img width="400" alt="thisprojectwascodedbyahumanbeing-wordart" src="https://github.com/user-attachments/assets/2e36f279-91d9-4f65-9c8f-fd8e6b179f7a" />

This is a thing that makes fancy ANSI graphics out of image files. And not just by sloppily repeating the same character all over the place; no, it detects transparency and draws edges with `.od$$o.o$$bo.` etc, like a real little ANSI artist.

It's an almost complete rewrite of an old project of mine. It's pretty versatile. You can adjust sizes, colour balance, contrast, define your own colour converters, shape sets, etc. There is [a CLI](packages/cli) for converting arbitrary images and making all kinds of adjustments, and [another one](packages/emoji) for emojis and flags. And more to come (?).

More info will probably come soon.

<img width="700" height="800" alt="image" src="https://github.com/user-attachments/assets/9f55bc2d-92d0-490a-87b4-e4ad501d519f" />

## Optimization/benchmarking

### Image resizing methods

Benchmarking the different `PIL.Image.Resampling` methods when downsizing an 1833x1380 image to 18x13:

```
NEAREST: 3.05 μs ± 50.6 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
BOX: 3.93 ms ± 48.8 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)
HAMMING: 7.28 ms ± 24 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)
BILINEAR: 7.3 ms ± 137 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)
BICUBIC: 13.3 ms ± 43.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)
LANCZOS: 19.5 ms ± 34.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)
```

(`NEAREST` is **more than a thousand** times faster than the runner-up!)

And when upsizing the same image to 18300x13800:

```
NEAREST: 696 ms ± 11.5 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
BOX: 1.75 s ± 11.7 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
BILINEAR: 2.13 s ± 48.6 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
HAMMING: 2.13 s ± 16.6 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
BICUBIC: 2.88 s ± 14.4 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
LANCZOS: 3.69 s ± 121 ms per loop (mean ± std. dev. of 7 runs, 1 loop each)
```

(Just a 2.5x lead for `NEAREST` here.)

### Image section colour inference methods

Inferring colour for an RGBA array of shape=(29, 4):

```
MEDIAN: 2.11 μs ± 29.1 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
MOST-COMMON: 25.4 μs ± 910 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)
```

`ColorInferenceMethod.MEDIAN` is more than 10x faster.
