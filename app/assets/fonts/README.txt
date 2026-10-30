Bundled fonts for the kinetic renderer (app/kinetic.py).

All three are SIL Open Font License 1.1, converted from woff2 to TTF so Pillow
can load them; the conversion only drops the WebFont wrapper, the glyphs are
unchanged.

* Inter Black (Inter-Black.ttf)      - body/labels, matches the site's Inter
* Anton Regular (Anton-Regular.ttf)  - the ultra-heavy condensed display face
* Archivo Black (ArchivoBlack-Regular.ttf) - alternate display face

Sources: npm packages @fontsource/inter 5.2.5, @fontsource/anton 5.2.5 and
@fontsource/archivo-black 5.2.5 (latin subsets). Licenses are OFL-1.1; see
https://openfontlicense.org. No font file here may be sold on its own.
