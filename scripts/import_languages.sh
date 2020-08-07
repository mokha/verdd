#!/bin/bash

### SETTINGS
APERTIUM_MONO_LANGS="fin deu eng por rus" # fra
GEILLA_LEXC_LANGS="apu izh kca kpv lav liv lut mdf mhr mrj myv mns nio olo skf sme smn sms udm vep vro yrk est-x-plamk"
APERTIUM_BI_LANGS="myv-mdf myv-fin kpv-koi kpv-fin fin-krl fin-olo krl-olo mrj-fin udm-rus" # udm-kpv
GEILLA_XML_LANGS="izh kca koi lav liv mdf mhr mrj myv nio olo sms vep vro yrk"              # udm
GIELLA_SVN_LANGS="deumyv engmdf engmyv estmyv estudm finudm udmfin koikpv kpvkoi kpvdeu kpvudm lavliv mdfeng mdfrus mhrrus mhrmrj myvdeu myveng myvest myvmdf olorus ruskpv rusmdf rusmyv rusolo rusvep smesmn smefin smnfin udmkpv vroest"
IGNORE_AFFILIATIONS="--ignore-affiliations" # speeds up imports as affiliations are not queried from akusanat.com

# create a local directory to import the files to
import_dir=$(mktemp -d)
current_dir=$(pwd)

# Git Clones
cd "$import_dir"

# Apertium imports
for lang in $APERTIUM_MONO_LANGS; do
  git clone "https://github.com/apertium/apertium-$lang.git"
done

# Geilla imports
for lang in $GEILLA_LEXC_LANGS; do
  git clone "https://github.com/giellalt/lang-$lang.git"
done

for lang in $APERTIUM_BI_LANGS; do
  git clone "https://github.com/apertium/apertium-$lang.git"
done

# Import Giella SVN xmls
GIELLA_SVN_DIR="giella-svn-xml"
mkdir -p "$import_dir/$GIELLA_SVN_DIR"
cd "$import_dir/$GIELLA_SVN_DIR"
for lang in $GIELLA_SVN_LANGS; do
  lang_dir="$import_dir/$GIELLA_SVN_DIR/$lang/"
  mkdir -p "$lang_dir"
  cd "$lang_dir"
  wget -r --quiet -A "*.xml" -l1 --no-parent -nH --cut-dirs=6 --reject="index.html*" "https://victorio.uit.no/langtech/trunk/words/dicts/$lang/src/"
done
cd "$import_dir"

# All custom imports should go here
CUSTOM_DIR="custom-xml"
mkdir "$CUSTOM_DIR"
cd "$CUSTOM_DIR"
git clone "https://github.com/rueter/kpv.git" "rueter-kpv"

# get back to current dir, then run import scripts
cd "$current_dir"

# Import monodix
for lang in $APERTIUM_MONO_LANGS; do
  echo "Processing Apertium-monodix ($lang)"
  python manage.py import_mono_dix -f "$import_dir/apertium-$lang/apertium-$lang.$lang.dix" -l "$lang" $IGNORE_AFFILIATIONS
done

# Import lexc
for lang in $GEILLA_LEXC_LANGS; do
  readarray -d '-' -t langs <<<"$lang"
  src_lang=$(echo "${langs[0]}" | tr -d '\n')
  echo "Processing Geilla-lexc ($lang)"
  python manage.py import_lexc -d "$import_dir/lang-$lang/src/fst/stems/" -l "$src_lang" $IGNORE_AFFILIATIONS
done

# Import bidix
for lang in $APERTIUM_BI_LANGS; do
  readarray -d '-' -t langs <<<"$lang"
  src_lang=$(echo "${langs[0]}" | tr -d '\n')
  tgt_lang=$(echo "${langs[1]}" | tr -d '\n')
  echo "Processing Apertium-bidix ($lang): $src_lang $tgt_lang"
  python manage.py import_dix -f "$import_dir/apertium-$lang/apertium-$lang.$lang.dix" -s "$src_lang" -t "$tgt_lang"
done

# Import xmls
for lang in $GEILLA_XML_LANGS; do
  echo "Processing Geilla-xml ($lang)"
  python manage.py import_giella_xml -d "$import_dir/lang-$lang/src/fst/stems/" $IGNORE_AFFILIATIONS
done

# Import Giella SVN xmls
for lang in $GIELLA_SVN_LANGS; do
  echo "Processing Geilla-svn-xml ($lang)"
  python manage.py import_giella_xml -d "$import_dir/$GIELLA_SVN_DIR/$lang/" $IGNORE_AFFILIATIONS
done

# Custom imports
python manage.py import_giella_xml -d "$import_dir/$CUSTOM_DIR/rueter-kpv/" $IGNORE_AFFILIATIONS

#wget "https://raw.githubusercontent.com/apertium/apertium-krl/master/apertium-krl.krl.lexc"

# remove imported files
rm -rf "$import_dir"
