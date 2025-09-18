// static/js/image_compress.js
// ============================
// Скрипт для сжатия изображений перед отправкой формы добавления/редактирования товара.
// Делает ресайз картинки до maxSize (по умолчанию 1080px по длинной стороне)
// и сохраняет её как JPEG с качеством ~80%.
// Также добавлен спиннер на кнопке "Сохранить", чтобы пользователь видел процесс.

// Функция сжатия изображения
async function compressImage(file, maxSize = 1080, quality = 0.8) {
    return new Promise((resolve) => {
      const reader = new FileReader();
  
      // Читаем выбранный файл как dataURL
      reader.onload = (e) => {
        const img = new Image();
  
        // Когда картинка загрузилась в память браузера
        img.onload = () => {
          const canvas = document.createElement("canvas");
          let width = img.width;
          let height = img.height;
  
          // Уменьшаем пропорционально до maxSize
          if (width > height) {
            if (width > maxSize) {
              height *= maxSize / width;
              width = maxSize;
            }
          } else {
            if (height > maxSize) {
              width *= maxSize / height;
              height = maxSize;
            }
          }
  
          // Задаём новые размеры для canvas
          canvas.width = width;
          canvas.height = height;
  
          // Рисуем картинку на canvas
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);
  
          // Сохраняем как JPEG
          canvas.toBlob(
            (blob) => {
              // Создаём новый File на основе сжатого blob
              const compressedFile = new File([blob], replaceExt(file.name, ".jpg"), {
                type: "image/jpeg",
                lastModified: Date.now(),
              });
              resolve(compressedFile); // возвращаем сжатый файл
            },
            "image/jpeg", // тип выходного файла
            quality       // качество (0.8 = 80%)
          );
        };
  
        // Подгружаем dataURL в объект Image
        img.src = e.target.result;
      };
  
      // Запускаем FileReader
      reader.readAsDataURL(file);
    });
  }
  
  // Вспомогательная функция: меняет расширение у имени файла
  function replaceExt(filename, newExt) {
    return filename.replace(/\.[^/.]+$/, "") + newExt;
  }
  
  // Когда DOM загружен
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("product-form");   // форма продукта
    const fileInput = document.getElementById("image-input"); // input type=file
    const saveBtn = document.getElementById("save-btn");      // кнопка "Сохранить"
    const spinner = document.getElementById("spinner");       // спиннер внутри кнопки
  
    if (form && fileInput) {
      // Ловим отправку формы
      form.addEventListener("submit", async (e) => {
        if (fileInput.files.length > 0) {
          e.preventDefault(); // стопим стандартную отправку
  
          // Показываем спиннер и дизейблим кнопку
          if (spinner) spinner.style.display = "inline-block";
          if (saveBtn) saveBtn.disabled = true;
  
          try {
            // Берём первый выбранный файл
            const file = fileInput.files[0];
  
            // Сжимаем файл
            const compressed = await compressImage(file);
  
            // Собираем новую FormData с подменённым файлом
            const formData = new FormData(form);
            formData.set("image", compressed);
  
            // Отправляем форму вручную через fetch
            const resp = await fetch(form.action, {
              method: form.method,
              body: formData,
            });
  
            // Если сервер вернул redirect → переходим
            if (resp.redirected) {
              window.location.href = resp.url;
            } else {
              // иначе просто обновляем страницу
              location.reload();
            }
          } catch (err) {
            console.error("Ошибка при загрузке:", err);
  
            // В случае ошибки возвращаем кнопку в нормальное состояние
            if (spinner) spinner.style.display = "none";
            if (saveBtn) saveBtn.disabled = false;
          }
        }
      });
    }
  });
  