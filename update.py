# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 19.12.2023
# Website: https://bespredel.name

import zipfile
import os
import shutil


def update(zip_file_path, destination_dir=os.getcwd()):
    if not os.path.exists(zip_file_path):
        print("Обновления не найдены.")
        return

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        # Получение списка файлов и папок в архиве
        update_contents = zip_ref.namelist()

        # Чтение содержимого файла update.txt (если он есть)
        if 'update.txt' in update_contents:
            update_file = zip_ref.open('update.txt')
            update_contents = update_file.read().decode('utf-8').splitlines()

        # Удаление файлов и папок, указанных в архиве или в update.txt
        for item in update_contents:
            file_path = os.path.join(destination_dir, item)
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)

        # Распаковка архива
        zip_ref.extractall(destination_dir)

    # Удаление архива
    os.remove(zip_file_path)

    print("Обновление успешно завершено.")


# Запуск функции обновления
update("update.zip")
