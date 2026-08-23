# resize-image-zipfile

Converts images in ZIP, CBZ, and RAR archives to WebP (quality 80), limiting
their width to 1280 pixels while preserving aspect ratio. Nested archives and
Unicode/Japanese filenames are supported. Nested RAR files are converted from
`name.rar` to `name.rar.zip` because the RAR format cannot be created by 7-Zip.

- Double-click `run_script.bat` to process archives beside the script.
- Drag one or more archives onto `drag_and_drop_zip.bat` to process them.
- RAR extraction requires 7-Zip (`7z.exe`) on `PATH`.
- Up to eight archives are processed concurrently. Run
  `run_script.bat --workers N` to choose a different limit.

Output is written beside each input as `<name>-1280x.zip`; inputs are not
modified. Temporary extraction folders are created under `.resize-temp` beside
the script, keeping them on the same drive, and are deleted after each run.
Successfully processed input archives are moved into a `processed-success`
subfolder, while failed inputs are moved into `processed-failed`. Generated
`-1280x.zip` outputs remain in the original location. Run results and full error
details are appended to `resize.log` beside the script.
