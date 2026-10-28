# HBM-LIVECAM

Bل؛£n ل»©ng dل»¥ng Windows ؤ‘ل»™c lل؛­p, chل»چn GPU CUDA cho xل»­ lأ½ hأ¬nh ل؛£nh/video vأ  live webcam. Bل»™ cأ i tل؛،o mأ´i trئ°ل»‌ng Python riأھng trong %LOCALAPPDATA%, khأ´ng sل»­a FM-OFS hay Python dأ¹ng chung. Bل»™ cأ i dأ¹ng Python hل»£p lل»‡ vأ  wheel tئ°ئ،ng thأ­ch cأ³ sل؛µn trأھn mأ،y trئ°ل»›c; chل»‰ lل؛¥y phل؛§n thئ° viل»‡n cأ²n thiل؛؟u. Pip cإ©ng dأ¹ng cache mل؛·c ؤ‘ل»‹nh cل»§a Windows.

## Cأ i ؤ‘ل؛·t

Giل؛£i nأ©n gأ³i, chل؛،y Install-HBM-LIVECAM.cmd. Bل»™ cأ i tأ¬m Python 3.12 hل»£p lل»‡ trأھn mأ،y; chل»‰ tل؛£i bل؛£n chأ­nh thل»©c nل؛؟u khأ´ng cأ³. Bل»™ xل»­ lأ½ chأ­nh dأ¹ng ONNX Runtime CUDA 13 vأ  thئ° viل»‡n CUDA/cuDNN runtime cل؛§n thiل؛؟t; khأ´ng cأ i PyTorch/TorchVision mل؛·c ؤ‘ل»‹nh ؤ‘ل»ƒ giل؛£m tل؛£i. PyTorch chل»‰ ؤ‘ئ°ل»£c dأ¹ng cho mل»™t sل»‘ tل»‘i ئ°u phل»¥ trل»£; thiل؛؟u nأ³, phل؛§n ghأ©p ل؛£nh dأ¹ng ؤ‘ئ°ل»‌ng xل»­ lأ½ dل»± phأ²ng. Bل»™ cأ i kiل»ƒm tra CUDA trئ°ل»›c khi tل؛،o lل»‘i tل؛¯t. Khأ´ng cل؛§n cأ i CUDA Toolkit riأھng.

InsightFace 0.7.3 ؤ‘ئ°ل»£c phأ،t hأ nh dئ°ل»›i dل؛،ng mأ£ nguل»“n trأھn PyPI. Nل؛؟u mأ،y khأ´ng cأ³ Microsoft C++ Build Tools, bئ°ل»›c biأھn dل»‹ch thئ° viل»‡n nأ y cأ³ thل»ƒ dل»«ng vأ  sل؛½ bأ،o lل»—i thay vأ¬ أ¢m thل؛§m chuyل»ƒn sang CPU.

## Camera vأ  OBS

Trong ل»©ng dل»¥ng, chل»چn camera, ؤ‘ل»™ phأ¢n giل؛£i, kأ­ch thئ°ل»›c dأ² mل؛·t vأ  giل»›i hل؛،n xل»­ lأ½ 15/24/30 FPS rل»“i bل؛¥m Live. Khung xem trل»±c tiل؛؟p vأ  tل»‡p ل؛£nh/video ؤ‘ل؛§u ra ؤ‘ئ°ل»£c ؤ‘أ³ng khung dل»چc 9:16 ل»ں 720x1280. Video ngang ؤ‘ئ°ل»£c cل؛¯t theo tأ¢m khung; preview webcam ئ°u tiأھn vأ¹ng mل؛·t khi nhل؛­n diل»‡n ؤ‘ئ°ل»£c. Mل؛·c ؤ‘ل»‹nh giل»›i hل؛،n 30 FPS. ؤگل»ƒ lل؛¥y hأ¬nh trong OBS, thأھm nguل»“n **Window Capture** vأ  chل»چn cل»­a sل»• xem trل»±c tiل؛؟p dل؛،ng dل»چc. Bل؛£n nأ y khأ´ng cأ i webcam ل؛£o/OBS plugin.

Model lئ°u bل»پn trong `%LOCALAPPDATA%\Programs\HBM-LIVECAM\models`; bل»™ cأ i chل»‰ bل»• sung file cأ²n thiل؛؟u, giل»¯ nguyأھn model vأ  file tل؛£i dل»ں khi cل؛­p nhل؛­t. InsightFace lئ°u tل؛،i `%USERPROFILE%\.insightface\models`.

## Mأ´ hأ¬nh

Khأ´ng kأ¨m model weights. Lل؛§n ؤ‘ل؛§u xل»­ lأ½, ل»©ng dل»¥ng tل؛£i model theo cئ، chل؛؟ upstream; model cأ³ giل؛¥y phأ©p/ؤ‘iل»پu khoل؛£n riأھng, cل؛§n xem ؤ‘iل»پu khoل؛£n cل»§a tل»«ng model trئ°ل»›c khi phأ¢n phل»‘i hoل؛·c dأ¹ng thئ°ئ،ng mل؛،i.

## Nguل»“n vأ  giل؛¥y phأ©p

Phل؛§n lأµi dل»±a trأھn [Deep-Live-Cam](https://github.com/hacksider/Deep-Live-Cam), giل؛¥y phأ©p AGPL-3.0; toأ n vؤƒn ل»ں LICENSE. Cأ،c thay ؤ‘ل»•i cل»§a gأ³i nأ y gل»“m tأھn/metadata, bل»™ cأ i CUDA hiل»‡n hأ nh, launcher riأھng vأ  tأ i liل»‡u cأ i ؤ‘ل؛·t. Phأ¢n phل»‘i bل؛£n sل»­a ؤ‘ل»•i cل؛§n tuأ¢n thل»§ AGPL-3.0, bao gل»“m cung cل؛¥p mأ£ nguل»“n tئ°ئ،ng ل»©ng.

