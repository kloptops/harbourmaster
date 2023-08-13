#!/bin/bash

# Directory where .pot file is located
POT_DIR="pylibs/locales"
POT_FILE="messages"

echo "Extracting strings ${POT_FILE}"
xgettext -v -o "${POT_DIR}/${POT_FILE}.pot" -L Python pugwash pylibs/harbourmaster/*.py

# pygettext.py -d libharbourmaster -o pylibs/locales/harbourmaster.pot pylibs/harbourmaster
# pygettext.py -d harbourmaster -o pylibs/locales/harbourmaster.pot harbourmaster

# Iterate over subdirectories (languages) in the LC_MESSAGES folder
for lang_dir in $POT_DIR/* ; do
    LANG_CODE=$(basename "$lang_dir")
    if [[ "${LANG_CODE}" != "." ]] && [[ "${LANG_CODE}" != ".." ]] && [ -d "$lang_dir" ]; then
        PO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.po"
        MO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.mo"

        # Check if the .po file exists
        if [ -f "$PO_FILE" ]; then
            echo "Updating translations for $LANG_CODE..."
            
            # Perform msgmerge
            msgmerge --no-fuzzy-matching --verbose -U "${PO_FILE}" "${POT_DIR}/${POT_FILE}.pot"
        else
            echo "Creating empty translation for $LANG_CODE"

            cp -v "${POT_DIR}/${POT_FILE}.pot" "${PO_FILE}"
        fi

        # Compile .po file into .mo file
        msgfmt -v -o "${MO_FILE}" "${PO_FILE}"
    fi
done
