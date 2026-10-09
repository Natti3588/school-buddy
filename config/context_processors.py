# システム名・キャッチコピー（名前が決まったらここだけ変更）
SYSTEM_NAME = "放課GO"
TAGLINE = "先生の校務を、もっとシンプルに"


def site(request):
    # 全テンプレートで system_name / tagline を使えるようにする
    return {"system_name": SYSTEM_NAME, "tagline": TAGLINE}
