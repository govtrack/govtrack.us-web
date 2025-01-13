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

# jQuery Lazy
download \
  https://raw.github.com/eisbehr-/jquery.lazy/master/jquery.lazy.min.js \
  $VENDOR/jquery.lazy.min.js \
  '64fbc7f830625ecd6ff3293b96665aebec2a9be9336f02fd47508eb59f7ec23a'

# Bootstrap (MIT License)
download \
  https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css \
  $VENDOR/bootstrap.min.css \
  'c0bcf7898fdc3b87babca678cd19a8e3ef570e931c80a3afbffcc453738c951a'
download \
  https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js \
  $VENDOR/bootstrap.bundle.min.js \
  '9520018fa5d81f4e4dc9d06afb576f90cbbaba209cfcc6cb60e1464647f7890b'

# Font Awesome (for the spinner on ajax calls, various icons; MIT License)
download \
  https://use.fontawesome.com/releases/v6.6.0/fontawesome-free-6.6.0-web.zip \
  /tmp/fontawesome.zip \
  'f425638f6db13622074ccd9369941170935a40891094b6505c5bc28c29f028eb'
(cd /tmp; unzip fontawesome.zip;)
mv /tmp/fontawesome-free-6.6.0-web $VENDOR/fontawesome

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
  'de5220a36ff16ffb199458d4d0e22d7d8f4f0aece57b7fe9050fee712e6b7d61'
download \
  https://code.highcharts.com/modules/accessibility.js \
  $VENDOR/highcharts-accessibility.js \
  '68d66bcbabca1ee7e73dff7df485b358d079d85c033c58bfdbb4bb630f374d13'
download \
  https://code.highcharts.com/modules/xrange.js \
  $VENDOR/highcharts-xrange.js \
  'a4dd5b4ce4f41e555d6603a0235fa5661e37b0df6d9510eeffd662a938193ddf'

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
# TODO: Requires bash v4 not available on macOS. Also it returns with a non-zero
# exit status ("Failed to determine local font name") but it works, so ignore
# exit status with || true
download \
  https://raw.githubusercontent.com/neverpanic/google-font-download/ba0f7fd6de0933c8e5217fd62d3c1c08578b6ea7/google-font-download \
  /tmp/google-font-download \
  '1f9b2cefcda45d4ee5aac3ff1255770ba193c2aa0775df62a57aa90c27d47db5'
(cd $VENDOR; bash /tmp/google-font-download -f woff,woff2 -o google-fonts.css \
  "Public Sans:300" "Public Sans:700" "IBM Plex Serif:400") || true
rm -f /tmp/google-font-download
# generated with:
# sha256sum static/vendor/{google-fonts.css,*woff*} | sed s"#static/vendor#\$VENDOR#"
$SHACMD_CHECK << EOF
c533160dfaa3672313040bb01372f9a1940476c023af99b167bfc926fb879375  $VENDOR/google-fonts.css
418c8c851f89d2c8750d3291d1c4d7a728fc4dc6e96e4e05757f426fbbf99572  $VENDOR/IBM_Plex_Serif_400.woff
256774147c18fde1089393e4008316d583dd0fe5f5aacc9438b23640ce1c552a  $VENDOR/IBM_Plex_Serif_400.woff2
2bce22a0c5820ccb6a8361f2351ac653114b8db1a228f666f21584126024beb5  $VENDOR/Public_Sans_300.woff
43493d1ab775f9889358c6df1bc8d88227edc90b07d864bb765298bd47da7ed1  $VENDOR/Public_Sans_300.woff2
99ca49a60694ac4b6c446edf683f35df2b7526fee627fe9a017d29f2198d98b0  $VENDOR/Public_Sans_700.woff
060efad3a20c5fbce28790fca46a54496ac35733e72484cab36bf37344054e66  $VENDOR/Public_Sans_700.woff2
EOF
