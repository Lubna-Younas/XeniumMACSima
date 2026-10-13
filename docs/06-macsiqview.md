# 06 — MACSiQ View import validation (pending)

An ASHLAR multichannel OME-TIFF is the output of this release. It is not yet a verified replacement for the native MACSiQ View experiment directory.

The next adapter should use a separately inspected, accepted native dataset as a **format reference**, without copying unrelated tissue metadata. Required checks include ROI/cycle/stage/channel filenames, channel identities, physical pixel size, shared canvas positions, per-channel uint16 image planes, pyramids, OME references, provenance and directory layout.

Validate exported base pixels against their ASHLAR source channel, verify pyramids and metadata, then load the result in the actual target MACSiQ View version. Confirm channel labels, scale, orientation, cycle overlay and ROI navigation visually. Record the application version and import result. Do not retain native claims of flat-field, optical-distortion correction or denoising if those operations were not performed.

An earlier separate export prototype exists in the source project but is deliberately not promoted here as a validated import path. This release's cluster wrapper does not create native exports. Scientific human review remains necessary even after a successful import.
