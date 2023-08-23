#!/bin/bash

# Directory where .pot file is located
POT_DIR="pylibs/locales"
POT_FILE="messages"

echo "Extracting strings ${POT_FILE}"
xgettext -v -o "${POT_DIR}/${POT_FILE}.pot" -L Python pugwash pylibs/harbourmaster/*.py pylibs/pug*.py

# pygettext.py -d libharbourmaster -o pylibs/locales/harbourmaster.pot pylibs/harbourmaster
# pygettext.py -d harbourmaster -o pylibs/locales/harbourmaster.pot harbourmaster

# Iterate over subdirectories (languages) in the LC_MESSAGES folder
for lang_dir in $POT_DIR/* ; do
    LANG_CODE=$(basename "$lang_dir")
    if [[ "${LANG_CODE}" != "." ]] && [[ "${LANG_CODE}" != ".." ]] && [ -d "$lang_dir" ]; then
        echo "${LANG_CODE}:"

        PO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.po"
        MO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.mo"

        # Check if the .po file exists
        if [ -f "$PO_FILE" ]; then
            printf "msgmerge: "
            # Perform msgmerge
            msgmerge --no-fuzzy-matching --verbose -U "${PO_FILE}" "${POT_DIR}/${POT_FILE}.pot"
        else
            mkdir -p "$lang_dir/LC_MESSAGES"
            printf "copying tempalte: "
            cp -v "${POT_DIR}/${POT_FILE}.pot" "${PO_FILE}"
        fi

        # Compile .po file into .mo file
        printf "msgfmt: "
        msgfmt -v -o "${MO_FILE}" "${PO_FILE}"

        echo ""
    fi

done
