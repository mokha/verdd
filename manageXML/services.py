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
    # Get a list of all files in the directory
    files_in_dir = [
        f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))
    ]

    # Check if there is exactly one .zip file in the directory
    zip_files = [f for f in files_in_dir if f.endswith(".zip")]

    if len(zip_files) == 1:
        # If there's exactly one .zip file, return its content directly
        zip_file_path = os.path.join(dir_path, zip_files[0])
        with open(zip_file_path, "rb") as single_zip_file:
            return single_zip_file.read()

    # Otherwise, zip the directory's contents as usual
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Walk the directory tree
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                # Create the full file path by joining root and file
                full_path = os.path.join(root, file)
                # Add the file to the zip archive
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
    elif download_type == DOWNLOAD_TYPE_LATEX:
        return generate_latex_file(
            source_language=lang1, target_language=lang2, approved=approved
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


def generate_latex_file(
    source_language: str, target_language: str, approved: bool = False
):
    with tempfile.TemporaryDirectory() as tmpdir_name:

        command = [
            "export_latex",
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
