#!/bin/bash

# Directory where .pot file is located
POT_DIR="pylibs/locales"
POT_FILE="messages"

echo "Extracting strings ${POT_FILE}"
xgettext -v -o "${POT_DIR}/${POT_FILE}.pot" -L Python pugwash pylibs/harbourmaster/*.py pylibs/pug*.py

crowdin upload

# pygettext.py -d libharbourmaster -o pylibs/locales/harbourmaster.pot pylibs/harbourmaster
# pygettext.py -d harbourmaster -o pylibs/locales/harbourmaster.pot harbourmaster

# Iterate over subdirectories (languages) in the LC_MESSAGES folder
for lang_dir in $POT_DIR/* ; do
    LANG_CODE=$(basename "$lang_dir")
    if [[ "${LANG_CODE}" != "." ]] && [[ "${LANG_CODE}" != ".." ]] && [ -d "$lang_dir" ]; then

        PO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.pot"
        MO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.mo"

        # Check if the .po file exists
        if [ -f "$PO_FILE" ]; then
            mkdir -p "$lang_dir/LC_MESSAGES"
            cp -v "${POT_DIR}/${POT_FILE}.pot" "${PO_FILE}"
        fi
    fi
done

crowdin download

for lang_dir in $POT_DIR/* ; do
    LANG_CODE=$(basename "$lang_dir")
    if [[ "${LANG_CODE}" != "." ]] && [[ "${LANG_CODE}" != ".." ]] && [ -d "$lang_dir" ]; then
        echo "${LANG_CODE}:"

        LANG_POT_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.pot"
        LANG_PO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.po"
        LANG_MO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.mo"

        mv -fv "$LANG_POT_FILE" "$LANG_PO_FILE"

        # Compile .po file into .mo file
        printf "msgfmt: "
        msgfmt -v -o "${LANG_MO_FILE}" "${LANG_PO_FILE}"

        echo ""
    fi

done
