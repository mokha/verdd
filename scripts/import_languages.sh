#!/bin/bash

### SETTINGS
APERTIUM_MONO_LANGS="fin deu eng fra por rus"
GEILLA_LEXC_LANGS="apu izh kca kpv lav liv lut mdf mhr mrj myv mns nio olo skf sme smn sms udm vep vro yrk est"
APERTIUM_BI_LANGS="myv-mdf myv-fin kpv-koi kpv-fin fin-krl fin-olo krl-olo mrj-fin udm-rus" # udm-kpv
GEILLA_XML_LANGS="izh kca koi lav liv mdf mhr mrj myv nio olo sms udm vep vro yrk"
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

# Import Giella SVN xmls
GIELLA_SVN_DIR="giella-svn-xml"
cd "$GIELLA_SVN_DIR"
for lang in $GIELLA_SVN_LANGS; do
  wget -r -A "*.xml" -l1 --no-parent -nH --cut-dirs=6 --reject="index.html*" "https://victorio.uit.no/langtech/trunk/words/dicts/$lang/src/"
done
cd ..

# All custom imports should go here
CUSTOM_DIR="custom-xml"
mkdir "$CUSTOM_DIR"
cd "$CUSTOM_DIR"
git clone "https://github.com/rueter/kpv.git" "rueter-kpv"
cd ..

# get back to current dir, then run import scripts
cd "$current_dir"

# Import monodix
for lang in $APERTIUM_MONO_LANGS; do
  echo "Processing Apertium-monodix ($lang)"
  python manage.py import_mono_dix -f "$import_dir/apertium-$lang/apertium-$lang.$lang.dix" -l "$lang" $IGNORE_AFFILIATIONS
done

# Import lexc
for lang in $GEILLA_LEXC_LANGS; do
  echo "Processing Geilla-lexc ($lang)"
  python manage.py import_mono_dix -d "$import_dir/lang-$lang/src/fst/stems/" -l "$lang" $IGNORE_AFFILIATIONS
done

# Import bidix
for lang in $APERTIUM_BI_LANGS; do
  readarray -d '-' -t langs <<<"$lang"
  src_lang="${langs[0]}"
  tgt_lang="${langs[1]}"
  echo "Processing Apertium-bidix ($lang): $src_lang $tgt_lang"
  python manage.py import_dix -f "$import_dir/apertium-$lang/apertium-$lang.$lang.dix" -s "$src_lang" -t "$tgt_lang"
done

# Import xmls
for lang in $GEILLA_XML_LANGS; do
  echo "Processing Geilla-xml ($lang)"
  python manage.py import_giella_xml -d "$import_dir/lang-$lang/src/fst/stems/" $IGNORE_AFFILIATIONS
done

# Import Giella SVN xmls
echo "Processing Geilla-svn-xml ($lang)"
python manage.py import_giella_xml -d "$import_dir/$GIELLA_SVN_DIR/" $IGNORE_AFFILIATIONS

# Custom imports
python manage.py import_giella_xml -d "$import_dir/$CUSTOM_DIR/rueter-kpv/" $IGNORE_AFFILIATIONS

#wget "https://raw.githubusercontent.com/apertium/apertium-krl/master/apertium-krl.krl.lexc"

# remove imported files
rm -rf "$import_dir"
