#!/bin/bash

set -euo pipefail

VENDOR=static/vendor

SHACMD="sha256sum"
SHACMD_CHECK="$SHACMD --strict --check"
if ! command -v sha256sum > /dev/null 2>&1 ; then
  # On macOS, sha256sum is not available. Use `shasum -a 256` instead.
  # But shasum doesn't support --strict and uses --warn instead.
  SHACMD="shasum -a 256"
  SHACMD_CHECK="$SHACMD --warn --check"
fi

function download {
  # Downloads a file from the web and checks that it matches
  # a provided hash. If the comparison fails, exit immediately.
  # Usage: download https://path/to/file /tmp/save-as.tgz ABCEDF12345_THE_HASH
  URL=$1
  DEST=$2
  HASH=$3
  CHECKSUM="$HASH  $DEST"
  rm -f $DEST

  echo $URL...
  curl -# -L -o $DEST $URL
  echo

  if ! echo "$CHECKSUM" | $SHACMD_CHECK > /dev/null; then
    echo "------------------------------------------------------------"
    echo "Download of $URL did not match expected checksum."
    echo "Found:"
    $SHACMD $DEST
    echo
    echo "Expected:"
    echo "$CHECKSUM"
    rm -f $DEST
    exit 1
  fi
}


# Clear any existing vendor resources.
rm -rf $VENDOR

# Create the directory.
mkdir -p $VENDOR

# Fetch resources.

# jQuery (MIT License)
download \
  https://code.jquery.com/jquery-3.4.1.min.js \
  $VENDOR/jquery.js \
  '0925e8ad7bd971391a8b1e98be8e87a6971919eb5b60c196485941c3c1df089a'

# Bootstrap (MIT License)
download \
  https://github.com/twbs/bootstrap/releases/download/v3.4.1/bootstrap-3.4.1-dist.zip \
  /tmp/bootstrap.zip \
  'd49793cf773cbd393ac2cf340c3b4ddab5365fa7c292098ac07e12eab3efd92e'
unzip -d /tmp /tmp/bootstrap.zip
mv /tmp/bootstrap-3.4.1-dist $VENDOR/bootstrap
rm -f /tmp/bootstrap.zip

# Font Awesome (for the spinner on ajax calls, various icons; MIT License)
download \
  https://use.fontawesome.com/releases/v5.0.13/js/all.js \
  $VENDOR/fontawesome.js \
  'e629fd9f6785d9a4cb5f5cc1cd3d3a758f35ad8c4451de510169e82a6dc4c78e'

# Josh's Bootstrap Helpers (MIT License)
# When this (client side JS) is updated, you must also
# update templates/bootstrap-helpers.html, which is the
# corresponding HTML.
download \
  https://raw.githubusercontent.com/JoshData/html5-stub/b3c62ad/static/js/bootstrap-helpers.js \
  $VENDOR/bootstrap-helpers.js \
  'ee9d222656eef25ad5e7b0e960a5c363d18084ca333c910e8c81579c45ca4ba5'

# Highcharts (proprietary but we purchased a license a long time ago)
download \
  https://code.highcharts.com/highcharts.js \
  $VENDOR/highcharts.js \
  'f56cbeafd29a5e57ab3b9da40a657efae3cf7f9cbd3f8f53eec3ce83d91f2c78'
download \
  https://code.highcharts.com/modules/accessibility.js \
  $VENDOR/highcharts-accessibility.js \
  '16df83b0a38e32c612e334b69e474d1728c521a92422193340daee17b74b61db'

# Plotly (MIT license)
download \
  https://cdn.plot.ly/plotly-1.38.1.min.js \
  $VENDOR/plotly.min.js \
  '009e098df216c03d5fac3303218ba0aec71a840d07b4a52fcb0e25fe44177512'

# bootstrap-responsive-tabs (MIT License)
download \
  https://raw.githubusercontent.com/openam/bootstrap-responsive-tabs/052b957e72ca0d4954813809c2dba21f5afde072/js/responsive-tabs.js \
  $VENDOR/bootstrap-responsive-tabs.js \
  '686ed86b10ad84abf3c5d4900f64998ff3f2a2f8765dc2b3032f23d91548df07'

# emojione (EmojiOne "Free License" https://github.com/emojione/emojione-assets/blob/master/LICENSE.md)
EMOJIONE_BASEURL=https://raw.githubusercontent.com/emojione/emojione-assets/3.1.2/sprites
mkdir $VENDOR/emojione
download \
  $EMOJIONE_BASEURL/emojione-sprite-24.min.css \
  $VENDOR/emojione/emojione-sprite-24.min.css \
  '9643c4f2b950f462f71ea15ffab848c949f3fe72a8a4a01e0a082f4d580ac754'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-people.png \
  $VENDOR/emojione/emojione-sprite-24-people.png \
  'f4324a31aabc175b083d4c136c6cd28fd0718f10d77519ba47525f1efee251b6'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-people\%402x.png \
  $VENDOR/emojione/emojione-sprite-24-people@2x.png \
  '031c43fb61be40004e1a2a1dc379fe7e0ade4cbf2998e10c9077950f1a58e8c5'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-objects.png \
  $VENDOR/emojione/emojione-sprite-24-objects.png \
  'b2a66a73e1a4c14a6b637a987d942c6b676c6033b365efc370fa9fc1a6fa8c8f'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-objects\%402x.png \
  $VENDOR/emojione/emojione-sprite-24-objects@2x.png \
  '40ac2aa1a1b90494431990689a69d8e114a7de27d5b8a6121fe0ce9f1f8b3e97'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-symbols.png \
  $VENDOR/emojione/emojione-sprite-24-symbols.png \
  '21f2268645db0cf8b5fae40b3c6263840558da4d9277ecac72adbf44fddbea22'
download \
  $EMOJIONE_BASEURL/emojione-sprite-24-symbols\%402x.png \
  $VENDOR/emojione/emojione-sprite-24-symbols@2x.png \
  '4a2d61983164c43c33dc9b2af772447175fee8ad236d430f385caf3b79184661'
# make empty files for other sprites because Django's ManifestStaticFilesStorage will bail during collectstatic
# if any assets mentioned in any CSS files (namely emojione-sprite-24.min.css) are not present.
for sprite in nature food activity travel flags regional diversity; do
  touch $VENDOR/emojione/emojione-sprite-24-$sprite.png $VENDOR/emojione/emojione-sprite-24-$sprite@2x.png
done

# google fonts
#  Hind: SIL Open Font License 1.1
# first download a helper (note: we're about to run a foreign script locally)
# TODO: Requires bash v4 not available on macOS.
download \
  https://raw.githubusercontent.com/neverpanic/google-font-download/ba0f7fd6de0933c8e5217fd62d3c1c08578b6ea7/google-font-download \
  /tmp/google-font-download \
  '1f9b2cefcda45d4ee5aac3ff1255770ba193c2aa0775df62a57aa90c27d47db5'
(cd $VENDOR; bash /tmp/google-font-download -f woff,woff2 -o google-fonts.css Quicksand:500 Roboto\ Slab:300 Roboto\ Slab:700 Titillium\ Web:600)
rm -f /tmp/google-font-download
# generated with: `$SHACMD $VENDOR/{google-fonts.css,*woff*}` but then put the vendor path variable back
$SHACMD_CHECK << EOF
0b411e96ea4997ca7719e9bae7b429aae5cb4881797851f28c2437bd3d85d951  $VENDOR/google-fonts.css
91925c6009a0039bd0e9c07f75253d81598a3c09a3bf498662c935c674bfeaee  $VENDOR/Quicksand_300.woff
38c8d523d1f60d51bd199b06b4a5bc573a3ba9c5e29ca9e5dbd85fcb7460bc15  $VENDOR/Quicksand_300.woff2
6c47a63b3c201d2a10e5e5ae682fca66dc70b955360798595fc8210ea23c97f4  $VENDOR/Roboto_Slab_300.woff
07844b19245182986c98527d35f1fe21e853a835eb8a80c722113e02e406af7e  $VENDOR/Roboto_Slab_300.woff2
5b49f1ffb26d12c79f7aa26a4437738df7eb0aa52d2e15c3f2a3ed160824a728  $VENDOR/Roboto_Slab_700.woff
03a7369d68b1d2ec09b9397b0710d90d4a6efcd33450a87ad618ec8eb2b83c7a  $VENDOR/Roboto_Slab_700.woff2
af9e0b9fd33062e183365997f895c209635af774242d1702146b4027aa3d6462  $VENDOR/Titillium_Web_600.woff
ef8a5f444c988e2c08260642c8257654f5e825e839a9c3d355933d4d12e0345b  $VENDOR/Titillium_Web_600.woff2
EOF
