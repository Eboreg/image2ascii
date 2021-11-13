# image2ascii

Converts images to ASCII, with a twist; it traces edges in the image and attempts to render them with suitably formed characters, à la good old handmade ASCII art:

```
                     ..
                .od$P°°?$bod°?b.
             .odP°    P°  °b  °$
           .d$P o  $.o$    $  .$
          d$P  d°  °$ °b..ob.dP?.
         .$P  d°    $.  °°  .oo.$.
         d$°  $     °b      $$$$$b.
        .$P   $      $      °?$$P$b
        d$°   °?ooooP°           ?$.
        ?$.     o  o             °$b
        °$b    .$  $.             $$
         ?$.   d   .B            .$P
          ?$    °?P°            .d°
           °?b.              ..od°
          .dP °?bo.       .od°°
         do.odP°°?$b  oo  $°
                  $I  I$  $
                  $I  I$  $
                  $I  I$  °bo.
                 .$I   °bo. .P
                 dP     .dPd°
                 °?booood°
```

It can also crop, output ANSI colour, adjust contrast/colour balance/brightness, invert, and other nice stuff. `cli.main` will install itself as a `image2ascii` command, check it out for more info. Play around with various combinations of `--invert`, `--invert-colors`, and `--swap-bw` until the results are to your liking.

This project is totally in alpha and makes no guarantees for anything whatsoever.

Uses:
* [Pillow](https://python-pillow.org/)
* [Matplotlib](https://matplotlib.org/)
* [Colorama](https://github.com/tartley/colorama)
