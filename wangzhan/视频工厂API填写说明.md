# 瑙嗛宸ュ巶 API 濉啓璇存槑

浣犲彧闇€瑕佹敼杩欎釜鏂囦欢锛?
```text
{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server/.env
```

鍦?`.env` 閲屾壘鍒帮細

```text
# 瑙嗛宸ュ巶 API 閰嶇疆鍖?```

鐒跺悗濉啓涓嬮潰杩欎簺鍙橀噺銆?
## 1. GPT 涓浆绔?
鐢ㄤ簬鐢熸垚鑴氭湰銆佸垎闀滃拰 Veo prompt銆?
```text
VIDEO_FACTORY_GPT_BASE_URL=
VIDEO_FACTORY_GPT_API_KEY=
VIDEO_FACTORY_GPT_MODEL=
VIDEO_FACTORY_GPT_API_PATH=/chat/completions
VIDEO_FACTORY_GPT_API_STYLE=chat_completions
```

濡傛灉浣犵殑涓浆绔欐槸 OpenAI 鍏煎鎺ュ彛锛屼竴鑸繚鎸侊細

```text
VIDEO_FACTORY_GPT_API_PATH=/chat/completions
VIDEO_FACTORY_GPT_API_STYLE=chat_completions
```

濡傛灉浣犵殑涓浆绔欒姹傝蛋 Responses 鎺ュ彛锛屽啀鏀规垚锛?
```text
VIDEO_FACTORY_GPT_API_PATH=/responses
VIDEO_FACTORY_GPT_API_STYLE=responses
```

## 2. gpt-image-2 涓浆绔?
鐢ㄤ簬鐢熸垚鍏抽敭甯у弬鑰冨浘銆?
```text
VIDEO_FACTORY_IMAGE_BASE_URL=
VIDEO_FACTORY_IMAGE_API_KEY=
VIDEO_FACTORY_IMAGE_MODEL=gpt-image-2
VIDEO_FACTORY_IMAGE_API_PATH=/images/generations
VIDEO_FACTORY_IMAGE_SIZE=1024x1792
```

## 3. Veo 涓浆绔?
鐢ㄤ簬鐢熸垚瑙嗛鐗囨銆?
```text
VIDEO_FACTORY_VEO_BASE_URL=
VIDEO_FACTORY_VEO_API_KEY=
VIDEO_FACTORY_VEO_MODEL=veo-3.0-generate-001
VIDEO_FACTORY_VEO_API_PATH=/v1/videos
VIDEO_FACTORY_VEO_STATUS_API_PATH=/v1/videos/{task_id}
VIDEO_FACTORY_VEO_REQUEST_FORMAT=openai
VIDEO_FACTORY_VEO_GENERATE_AUDIO=true
VIDEO_FACTORY_VEO_MAX_CLIPS_PER_TASK=1
VIDEO_FACTORY_VEO_WAIT_FOR_COMPLETION=true
```

褰撳墠宸查獙璇?`ai.ai666.net` 鐨?Veo 涓浆鎺ュ彛闇€瑕侊細

```text
VIDEO_FACTORY_VEO_API_PATH=/v1/videos
VIDEO_FACTORY_VEO_STATUS_API_PATH=/v1/videos/{task_id}
VIDEO_FACTORY_VEO_REQUEST_FORMAT=openai
```

绗竴鐗堣垂鐢ㄤ繚鎶わ細

```text
VIDEO_FACTORY_VEO_MAX_CLIPS_PER_TASK=1
```

琛ㄧず缃戦〉鐐光€滆繍琛屽伐浣滄祦鈥濇椂锛屽彧鐢熸垚绗?1 涓?Veo 鐗囨锛屽苟鎶婅繖涓?mp4 鐩存帴浣滀负鎴愮墖杩斿洖銆傚悗缁帴鍏?FFmpeg 鎷兼帴鍚庯紝鍐嶆妸杩欎釜鍊艰皟澶с€?
## 濉ソ鍚?
1. 淇濆瓨 `.env`
2. 閲嶅惎鍚庣
3. 鍛婅瘔鎴戔€滃～濂戒簡鈥?
鎴戜細甯綘娴嬭瘯锛?
```text
GET /api/v1/video/workflow/provider-status
```

鍐嶈窇瑙嗛宸ュ巶鐨勬渶灏忕湡瀹炶皟鐢ㄩ摼璺€?
## 椤甸潰妯″瀷閫夋嫨

鐜板湪鍓嶇浼氳嚜鍔ㄨ鍙栵細

```text
GET /api/v1/video/workflow/provider-models
```

杩欎釜鎺ュ彛浼氱敤浣犲湪 `.env` 閲屽～鍐欑殑 `VIDEO_FACTORY_GPT_BASE_URL`銆乣VIDEO_FACTORY_IMAGE_BASE_URL`銆乣VIDEO_FACTORY_VEO_BASE_URL` 鍒嗗埆灏濊瘯璇锋眰涓浆绔欑殑 `/models`銆?
1. 濡傛灉涓浆绔欐敮鎸?`/models`锛屽彸渚ц妭鐐瑰弬鏁伴噷浼氬嚭鐜板彲閫夋ā鍨嬩笅鎷夈€?2. 濡傛灉涓浆绔欎笉鏀寔 `/models`锛岄〉闈細浣跨敤 `.env` 閲岀殑 `VIDEO_FACTORY_*_MODEL` 榛樿鍊笺€?3. 浣犲湪椤甸潰鍒囨崲妯″瀷鍚庯紝鏈宸ヤ綔娴佷細鎸夎妭鐐归€夋嫨鐨勬ā鍨嬭繍琛屻€?4. 鎯虫彁楂樻垚鐗囪川閲忥紝浼樺厛鍦?`Veo 瑙嗛鐢熸垚` 鑺傜偣閫夋嫨璐ㄩ噺鍨嬫ā鍨嬶紝灏戠敤鍚嶅瓧閲屽甫 `fast / flash / lite / mini` 鐨勬ā鍨嬨€?
娉ㄦ剰锛氫笉瑕佹妸 API key 鍙戝埌鑱婂ぉ閲屻€?
