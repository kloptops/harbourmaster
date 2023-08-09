#!/bin/bash

# Directory where .pot file is located
POT_DIR="pylibs/locales"
POT_FILES=("pugwash" "harbourmaster")

for POT_FILE in "${POT_FILES[@]}"; do
    echo "Extracting strings ${POT_FILE}"
    xgettext -v -o "${POT_FILE}.pot" -p "${POT_DIR}" -L Python "${POT_FILE}"
done

# pygettext.py -d libharbourmaster -o pylibs/locales/harbourmaster.pot pylibs/harbourmaster
# pygettext.py -d harbourmaster -o pylibs/locales/harbourmaster.pot harbourmaster

# Iterate over subdirectories (languages) in the LC_MESSAGES folder
for lang_dir in $POT_DIR/* ; do
    LANG_CODE=$(basename "$lang_dir")
    if [[ "${LANG_CODE}" != "." ]] && [[ "${LANG_CODE}" != ".." ]] && [ -d "$lang_dir" ]; then
        for POT_FILE in "${POT_FILES[@]}"; do
            PO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.po"
            MO_FILE="$lang_dir/LC_MESSAGES/${POT_FILE}.mo"

            # Check if the .po file exists
            if [ -f "$PO_FILE" ]; then
                echo "Updating translations for $LANG_CODE..."
                
                # Perform msgmerge
                msgmerge -v -U "${POT_DIR}/${POT_FILE}.pot" "${PO_FILE}"
                
                # Compile .po file into .mo file
                msgfmt -v -o "${MO_FILE}" "${PO_FILE}"
            fi
        done
    fi
done
