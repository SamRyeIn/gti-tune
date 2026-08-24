#!/bin/zsh
set -euo pipefail

ROOT=/Users/sam/SimosTools/Docs/simoscal-android-tutorial
BUILD=$ROOT/build
AUDIO=$BUILD/audio
FRAMES=$BUILD/frames
SCENES=$BUILD/scenes
NARRATION=$ROOT/narration
CALLOUTS=$ROOT/callouts

TOUR=/tmp/simoscal-tutorial-tour.mp4
LANDING=/tmp/simoscal-screen-test.mp4
BUILD_RUN=/tmp/simoscal-tutorial-build.mp4
ANALYSIS_RUN=/tmp/simoscal-tutorial-analysis3.mp4

TITLE_FONT=/System/Library/Fonts/SFNS.ttf
BODY_FONT=/System/Library/Fonts/SFNS.ttf
MONO_FONT=/System/Library/Fonts/SFNSMono.ttf

mkdir -p $AUDIO $FRAMES $SCENES

for SCRIPT in $NARRATION/*.txt; do
  STEM=${SCRIPT:t:r}
  say -v Samantha -r 176 -f $SCRIPT -o $AUDIO/$STEM.aiff
done

ffmpeg -y -hide_banner -loglevel error -ss 1 -i $LANDING -frames:v 1 $FRAMES/01-start-import.png
ffmpeg -y -hide_banner -loglevel error -ss 1 -i $TOUR -frames:v 1 $FRAMES/02-tables.png
ffmpeg -y -hide_banner -loglevel error -ss 5 -i $TOUR -frames:v 1 $FRAMES/03-boost.png
ffmpeg -y -hide_banner -loglevel error -ss 11 -i $TOUR -frames:v 1 $FRAMES/04-limiters.png
ffmpeg -y -hide_banner -loglevel error -ss 17 -i $TOUR -frames:v 1 $FRAMES/05-pedal.png
ffmpeg -y -hide_banner -loglevel error -ss 23 -i $TOUR -frames:v 1 $FRAMES/06-lambda.png
ffmpeg -y -hide_banner -loglevel error -ss 29 -i $TOUR -frames:v 1 $FRAMES/07-slots.png
ffmpeg -y -hide_banner -loglevel error -ss 37 -i $TOUR -frames:v 1 $FRAMES/08-changes.png
ffmpeg -y -hide_banner -loglevel error -ss 35 -i $BUILD_RUN -frames:v 1 $FRAMES/11-close.png

make_still_scene() {
  local NUMBER=$1
  local TITLE=$2
  local FRAME=$3
  local VOICE=$4
  local CALLOUT=$5
  local OUTPUT=$6

  ffmpeg -y -hide_banner -loglevel error \
    -f lavfi -i color=c=0x0B0E14:s=1920x1080:r=30 \
    -loop 1 -framerate 30 -i $FRAME \
    -i $VOICE \
    -filter_complex "\
      [1:v]crop=720:1152:0:64,scale=608:973[phone];\
      [0:v]drawbox=x=1226:y=32:w=656:h=1016:color=0x283242:t=2[frame];\
      [frame][phone]overlay=1250:54:shortest=1[screen];\
      [screen]drawtext=fontfile=${MONO_FONT}:text='simos':fontcolor=0xE9EEF5:fontsize=30:x=80:y=46,\
      drawtext=fontfile=${MONO_FONT}:text='cal':fontcolor=0xFF7A24:fontsize=30:x=164:y=46,\
      drawtext=fontfile=${BODY_FONT}:text='$NUMBER / 11':fontcolor=0xFF7A24:fontsize=24:x=80:y=112,\
      drawtext=fontfile=${TITLE_FONT}:text='$TITLE':fontcolor=0xE9EEF5:fontsize=58:x=80:y=156,\
      drawbox=x=80:y=242:w=1060:h=2:color=0x283242:t=fill,\
      drawtext=fontfile=${BODY_FONT}:textfile='$CALLOUT':fontcolor=0xA9B4C4:fontsize=32:line_spacing=18:x=80:y=294[v]" \
    -map '[v]' -map 2:a \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
    -c:a aac -b:a 192k -ar 48000 -ac 2 \
    -shortest -movflags +faststart $OUTPUT
}

make_video_scene() {
  local NUMBER=$1
  local TITLE=$2
  local SOURCE=$3
  local VOICE=$4
  local CALLOUT=$5
  local OUTPUT=$6

  ffmpeg -y -hide_banner -loglevel error \
    -f lavfi -i color=c=0x0B0E14:s=1920x1080:r=30 \
    -i $SOURCE \
    -i $VOICE \
    -filter_complex "\
      [1:v]crop=720:1152:0:64,scale=608:973,setpts=PTS-STARTPTS[phone];\
      [0:v]drawbox=x=1226:y=32:w=656:h=1016:color=0x283242:t=2[frame];\
      [frame][phone]overlay=1250:54:shortest=1[screen];\
      [screen]drawtext=fontfile=${MONO_FONT}:text='simos':fontcolor=0xE9EEF5:fontsize=30:x=80:y=46,\
      drawtext=fontfile=${MONO_FONT}:text='cal':fontcolor=0xFF7A24:fontsize=30:x=164:y=46,\
      drawtext=fontfile=${BODY_FONT}:text='$NUMBER / 11':fontcolor=0xFF7A24:fontsize=24:x=80:y=112,\
      drawtext=fontfile=${TITLE_FONT}:text='$TITLE':fontcolor=0xE9EEF5:fontsize=58:x=80:y=156,\
      drawbox=x=80:y=242:w=1060:h=2:color=0x283242:t=fill,\
      drawtext=fontfile=${BODY_FONT}:textfile='$CALLOUT':fontcolor=0xA9B4C4:fontsize=32:line_spacing=18:x=80:y=294[v]" \
    -map '[v]' -map 2:a \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
    -c:a aac -b:a 192k -ar 48000 -ac 2 \
    -shortest -movflags +faststart $OUTPUT
}

ffmpeg -y -hide_banner -loglevel error \
  -i $TOUR -i $ANALYSIS_RUN -i $AUDIO/00-hook.aiff \
  -f lavfi -i color=c=0x0B0E14:s=1920x1080:r=30:d=25 \
  -filter_complex "\
    [0:v]trim=start=0:end=44,setpts=0.454545*(PTS-STARTPTS),crop=720:1152:0:64,scale=608:973[tour];\
    [1:v]trim=start=68:end=88,setpts=0.25*(PTS-STARTPTS),crop=720:1152:0:64,scale=608:973[plots];\
    [tour][plots]concat=n=2:v=1:a=0[phone];\
    [3:v]drawbox=x=1226:y=32:w=656:h=1016:color=0x283242:t=2[frame];\
    [frame][phone]overlay=1250:54:shortest=1[screen];\
    [screen]drawtext=fontfile=${MONO_FONT}:text='simos':fontcolor=0xE9EEF5:fontsize=34:x=80:y=52,\
    drawtext=fontfile=${MONO_FONT}:text='cal':fontcolor=0xFF7A24:fontsize=34:x=175:y=52,\
    drawtext=fontfile=${BODY_FONT}:text='CALIBRATION. VERIFIED.':fontcolor=0xFF7A24:fontsize=25:x=80:y=144,\
    drawtext=fontfile=${TITLE_FONT}:text='Your calibration.':fontcolor=0xE9EEF5:fontsize=64:x=80:y=202,\
    drawtext=fontfile=${TITLE_FONT}:text='On the tablet.':fontcolor=0xE9EEF5:fontsize=64:x=80:y=278,\
    drawbox=x=80:y=382:w=1060:h=2:color=0x283242:t=fill,\
    drawtext=fontfile=${BODY_FONT}:text='EDIT  •  REVIEW  •  VERIFY  •  ANALYZE':fontcolor=0xA9B4C4:fontsize=30:x=80:y=430[v];\
    [2:a]apad=pad_dur=25,atrim=duration=25[a]" \
  -map '[v]' -map '[a]' \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -t 25 -movflags +faststart $SCENES/00-hook.mp4

make_still_scene 01 'START & IMPORT' $FRAMES/01-start-import.png $AUDIO/01-start-import.aiff $CALLOUTS/01-start-import.txt $SCENES/01-start-import.mp4
make_still_scene 02 'TABLES' $FRAMES/02-tables.png $AUDIO/02-tables.aiff $CALLOUTS/02-tables.txt $SCENES/02-tables.mp4
make_still_scene 03 'BOOST' $FRAMES/03-boost.png $AUDIO/03-boost.aiff $CALLOUTS/03-boost.txt $SCENES/03-boost.mp4
make_still_scene 04 'LIMITERS' $FRAMES/04-limiters.png $AUDIO/04-limiters.aiff $CALLOUTS/04-limiters.txt $SCENES/04-limiters.mp4
make_still_scene 05 'PEDAL FEEL' $FRAMES/05-pedal.png $AUDIO/05-pedal.aiff $CALLOUTS/05-pedal.txt $SCENES/05-pedal.mp4
make_still_scene 06 'FULL-LOAD LAMBDA' $FRAMES/06-lambda.png $AUDIO/06-lambda.aiff $CALLOUTS/06-lambda.txt $SCENES/06-lambda.mp4
make_still_scene 07 'MAP SLOTS' $FRAMES/07-slots.png $AUDIO/07-slots.aiff $CALLOUTS/07-slots.txt $SCENES/07-slots.mp4
make_still_scene 08 'CHANGES' $FRAMES/08-changes.png $AUDIO/08-changes.aiff $CALLOUTS/08-changes.txt $SCENES/08-changes.mp4
make_video_scene 09 'BUILD & EXPORT' $BUILD_RUN $AUDIO/09-build.aiff $CALLOUTS/09-build.txt $SCENES/09-build.mp4
make_video_scene 10 'ANALYZE DATALOGS' $ANALYSIS_RUN $AUDIO/10-analyze.aiff $CALLOUTS/10-analyze.txt $SCENES/10-analyze.mp4
make_still_scene 11 'THE COMPLETE LOOP' $FRAMES/11-close.png $AUDIO/11-close.aiff $CALLOUTS/11-close.txt $SCENES/11-close.mp4

ffmpeg -y -hide_banner -loglevel error \
  -f concat -safe 0 -i $ROOT/concat.txt \
  -c copy -movflags +faststart $ROOT/simoscal_android_tutorial.mp4
