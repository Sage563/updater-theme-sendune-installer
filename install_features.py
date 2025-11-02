from helper_module_features import *

def main():
    logging.info("Feature installer starting in %s", ROOT)
    manifest = read_manifest()

    try:
        packages = manifest.get("packages", [])
        install_packages(packages)

        files = manifest.get("files", [])
        copy_files(files)

        scripts = manifest.get("scripts", [])
        run_feature_scripts(scripts)

        logging.info("Feature installer completed successfully.")
    except Exception as e:
        logging.exception("Feature installer failed: %s", e)
        raise


if __name__ == "__main__":
    main()
