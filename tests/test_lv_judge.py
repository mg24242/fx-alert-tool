from src.lv_judge import judge_lv


def test_judge_lv_title_priority_and_strength():
    keywords = {
        "lv_keywords": {
            "lv4": ["断固たる", "断固"],
            "lv3": ["準備はできて"],
            "lv2": ["過度な変動"],
        }
    }

    # タイトル優先（本文にLv4があっても、タイトルにLv2があればLv2…ではなく、
    # 強度優先なのでタイトル内でもLv4>Lv3>Lv2の順で判定される）
    assert judge_lv("過度な変動に憂慮", "断固たる措置を検討", keywords) == 2

    # タイトル内にLv4があればLv4
    assert judge_lv("断固たる措置を示唆", "過度な変動", keywords) == 4

    # タイトルに無ければ本文を見る
    assert judge_lv("為替市場を注視", "準備はできている", keywords) == 3

    # どれにもマッチしなければLv1
    assert judge_lv("為替は安定的が望ましい", "市場を注視", keywords) == 1
