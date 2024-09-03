import zipfile
import os
import io
import tempfile
from django.core.management import call_command
from .constants import (
    DOWNLOAD_TYPE_GIELLA_XML,
    DOWNLOAD_TYPE_LATEX,
    DOWNLOAD_TYPE_APERTIUM_BIDIX,
    DOWNLOAD_TYPE_TRANSLATION_PREDICTIONS,
)


def run_django_command(command_name, *args, **kwargs):
    output = io.StringIO()
    call_command(command_name, *args, stdout=output, **kwargs)
    return output.getvalue()


def write_dir_content_to_zip(dir_path):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Walk the directory tree
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                # Create the full file path by joining root and file
                full_path = os.path.join(root, file)
                # Add the file to the zip archive
                # The arcname argument strips the base directory, so the file structure is preserved inside the zip
                arcname = os.path.relpath(full_path, start=dir_path)
                zip_file.write(full_path, arcname)

    zip_buffer.seek(0)

    return zip_buffer.getvalue()


def generate_file_for_request(download_type, lang1, lang2=None, approved=False):
    if download_type == DOWNLOAD_TYPE_GIELLA_XML:
        return generate_giella_xml(
            source_language=lang1, target_language=lang2, approved=approved
        )
    elif download_type == DOWNLOAD_TYPE_TRANSLATION_PREDICTIONS:
        return generate_translation_suggestions(
            source_language=lang1, target_language=lang2, approved=approved
        )
    elif download_type == DOWNLOAD_TYPE_APERTIUM_BIDIX:
        return generate_apertium_bidix(
            left_language=lang1, right_language=lang2, approved=approved
        )


def generate_giella_xml(
    source_language: str, target_language: str, approved: bool = False
):

    with tempfile.TemporaryDirectory() as tmpdir_name:

        command = [
            "export_xml_dict",
            "--dir",
            tmpdir_name,
            "--source",
            source_language,
            "--target",
            target_language,
        ]

        if approved:
            command.append("--approved")

        _ = run_django_command(*command)

        zip_result = write_dir_content_to_zip(tmpdir_name)

        return zip_result


def generate_apertium_bidix(
    left_language: str, right_language: str, approved: bool = False
):
    with tempfile.TemporaryDirectory() as tmpdir_name:

        command = [
            "export_dix",
            "--dir",
            tmpdir_name,
            "--left",
            left_language,
            "--right",
            right_language,
        ]

        if approved:
            command.append("--approved")

        _ = run_django_command(*command)

        zip_result = write_dir_content_to_zip(tmpdir_name)

        return zip_result


def generate_translation_suggestions(
    source_language: str, target_language: str, approved: bool = False
):
    with tempfile.TemporaryDirectory() as tmpdir_name:

        command = [
            "predict_translations",
            "--dir",
            tmpdir_name,
            "--source",
            source_language,
            "--target",
            target_language,
        ]

        if approved:
            command.append("--approved")

        _ = run_django_command(*command)

        zip_result = write_dir_content_to_zip(tmpdir_name)

        return zip_result


# def generate_latex_file(lang, use_accepted_lexemes):
#     result = run_django_command("my_command", "arg1", "arg2")
#     return result
