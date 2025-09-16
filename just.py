import os

# Путь к папке
folder = r"D:\work2\photo"

# Получаем список файлов
files = os.listdir(folder)

# Фильтруем только фото (например jpg, jpeg, png)
files = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png"))]

# Сортируем список (чтобы шли в правильном порядке)
files.sort()

# Переименовываем
for i, filename in enumerate(files, start=1):
    ext = os.path.splitext(filename)[1]  # расширение (.jpg/.png)
    new_name = f"{i}{ext}"
    src = os.path.join(folder, filename)
    dst = os.path.join(folder, new_name)
    os.rename(src, dst)
    print(f"{filename} → {new_name}")

print("✅ Все фото переименованы!")
