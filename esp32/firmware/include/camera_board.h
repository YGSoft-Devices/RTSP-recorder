#pragma once

#if defined(CAMERA_BOARD_AI_THINKER_OV2640)
#include "boards/ai_thinker_ov2640.h"
#elif defined(CAMERA_BOARD_CUSTOM_OV5640)
#include "boards/ov5640_template.h"
#else
#error "Aucun board caméra sélectionné. Définir CAMERA_BOARD_AI_THINKER_OV2640 ou CAMERA_BOARD_CUSTOM_OV5640."
#endif

