from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from marketplace.models import Artisan, Drop, Product


ARTISANS = [
    ("김민준", "바다와 산의 색에서 영감을 받아 차분한 생활 도자기를 빚습니다.", "도자기"),
    ("이지우", "부드러운 형태와 자연스러운 유약으로 작은 공예품을 만듭니다.", "생활 도자기"),
    ("박서연", "전통 물레 기법으로 오래 곁에 둘 그릇을 빚습니다.", "물레 성형"),
    ("최도윤", "자연에서 얻은 섬유로 따뜻한 생활 소품을 직조합니다.", "직물"),
    ("정하은", "단순한 실루엣과 흙의 질감을 살린 오브제를 만듭니다.", "세라믹"),
    ("강현우", "전통 기법에 현대적인 색을 더한 도자 작업을 합니다.", "도예"),
    ("윤채원", "손으로 짠 직물에 색과 이야기를 담아냅니다.", "직조"),
    ("임수빈", "아침의 작은 의식을 위한 머그와 찻잔을 빚습니다.", "생활 도자기"),
    ("한지훈", "매일 편하게 쓸 수 있는 단단하고 아름다운 그릇을 만듭니다.", "도자기"),
    ("오유나", "린넨과 천연 염색으로 오래 쓰는 패브릭을 만듭니다.", "천연 염색"),
    ("서준호", "섬세한 형태와 손그림 장식이 돋보이는 작품을 만듭니다.", "도자기"),
    ("문가은", "자연 소재를 엮어 오래 사용할 수 있는 생활 바구니를 만듭니다.", "위빙"),
    ("배시온", "따뜻한 흙빛과 유기적인 형태의 도자기를 탐구합니다.", "도예"),
    ("신예린", "재료의 본질과 손의 감각을 담은 홈 오브제를 만듭니다.", "홈웨어"),
]

PRODUCTS = [
    ("모래빛 아침 공기 (Dune Breakfast Bowl)", "따뜻한 모래빛 유약과 부드러운 곡선이 어우러진 아침 식사용 공기입니다.", "38000", 2),
    ("푸른 물결 에스프레소 잔 (Tide Espresso Cup)", "바다를 닮은 청록 유약을 입힌 손으로 빚은 작은 잔입니다.", "24000", 3),
    ("이끼빛 서빙 접시 (Moss Serving Plate)", "음식의 색을 돋보이게 하는 깊은 이끼빛 유약의 넉넉한 접시입니다.", "56000", 28),
    ("둥근 봉오리 화병 (Sculpted Bud Vase)", "자연스러운 비대칭 형태가 매력적인 한 점씩 다른 작은 화병입니다.", "42000", 5),
    ("매일의 세라믹 피처 (Everyday Pourer)", "손에 편안하게 잡히도록 균형 있게 빚은 데일리 피처입니다.", "48000", 24),
    ("린넨 테이블 러너 (Linen Table Runner)", "자연스러운 결이 살아 있는 린넨을 소량 직조해 만들었습니다.", "72000", 2),
    ("구름빛 차 잔 (Cloud Tea Cup)", "가벼운 질감과 아이보리 무광 유약이 돋보이는 차 잔입니다.", "30000", 3),
    ("황토빛 간식 접시 (Ochre Snack Plate)", "간단한 다과를 담기 좋은 작고 단단한 황토빛 접시입니다.", "28000", 26),
    ("손으로 짠 장바구니 (Woven Market Tote)", "시장 나들이와 일상에 두루 쓰기 좋은 튼튼한 핸드메이드 가방입니다.", "64000", 4),
    ("조약돌 인센스 홀더 (Pebble Incense Holder)", "매끄러운 조약돌에서 영감을 받은 작은 향 홀더입니다.", "22000", 20),
    ("올리브 오일 크루트 (Olive Oil Cruet)", "식탁 위에 작은 정성을 더해 주는 손마감 오일 병입니다.", "52000", 3),
    ("잔잔한 격자 쿠션 커버 (Soft Grid Cushion)", "차분한 자연색으로 짠 촉감 좋은 쿠션 커버입니다.", "88000", 5),
    ("라쿠 작은 소품 접시 (Raku Trinket Dish)", "독특한 유약 무늬가 하나뿐인 작은 소품 접시입니다.", "34000", 0),
    ("세이지 말차 사발 (Sage Matcha Bowl)", "자연스러운 입술선과 세이지빛 유약이 어우러진 말차 사발입니다.", "58000", 22),
    ("내추럴 코튼 냅킨 세트 (Natural Cotton Napkins)", "매일 세탁해 오래 쓸 수 있는 면 냅킨 네 장 세트입니다.", "36000", 8),
    ("투박한 흙빛 피처 (Rustic Clay Pitcher)", "손잡이와 철분이 감도는 유약에서 흙의 따뜻함이 느껴집니다.", "78000", 18),
    ("손으로 짠 월 행잉 (Woven Wall Hanging)", "염색하지 않은 울과 면을 천천히 엮은 벽 장식입니다.", "145000", 7),
    ("점박이 에스프레소 머그 (Speckled Espresso Mug)", "점박이 유약과 둥근 손잡이가 돋보이는 작은 에스프레소 머그입니다.", "26000", 30),
    ("손물레 파스타 볼 (Hand-thrown Pasta Bowl)", "넉넉한 양의 음식과 긴 점심을 담기 좋은 깊은 볼입니다.", "62000", 16),
    ("린넨 브레드 바스켓 (Linen Bread Basket)", "식탁 중앙에 빵을 담아 두기 좋은 부드러운 린넨 바스켓입니다.", "48000", 12),
    ("테라코타 오일 램프 (Terracotta Oil Lamp)", "흙의 조형미와 손마감이 돋보이는 오브제 조명입니다.", "86000", 2),
    ("강돌 비누 받침 (Riverstone Soap Dish)", "물 빠짐 홈을 더해 수제 비누를 보송하게 보관하는 받침입니다.", "24000", 25),
    ("인디고 티타월 세트 (Indigo Tea Towel Set)", "겹겹이 물든 인디고 색이 매력적인 면 타월 두 장입니다.", "42000", 21),
    ("조각 무늬 서빙 플래터 (Carved Serving Platter)", "가장자리를 손으로 다듬고 은은한 유약으로 마감한 긴 접시입니다.", "94000", 10),
    ("조형 인센스 버너 (Sculptural Incense Burner)", "건축적인 형태를 담아 손으로 빚은 스톤웨어 향 버너입니다.", "38000", 0),
    ("꼭두서니 염색 린넨 스카프 (Madder-dyed Linen Scarf)", "천연 꼭두서니 염료로 따뜻한 색을 입힌 가벼운 린넨 스카프입니다.", "68000", 15),
    ("플루티드 세라믹 화병 (Fluted Ceramic Vase)", "물레의 섬세한 세로 결과 분필빛 유약이 돋보이는 화병입니다.", "112000", 9),
    ("손으로 짠 컵받침 세트 (Woven Coaster Set)", "차분한 색의 면사를 짠 컵받침 네 장 세트입니다.", "32000", 32),
    ("손그림 버터 벨 (Hand-painted Butter Bell)", "손그림 장식이 더해진 전통 방식의 세라믹 버터 보관 용기입니다.", "46000", 3),
    ("포근한 울 블랭킷 (Knit Wool Throw)", "자연스러운 술 장식과 편안한 짜임의 부드러운 울 블랭킷입니다.", "198000", 6),
    ("낮은 스톤웨어 화분 (Low Stoneware Planter)", "배수 구멍과 이끼빛 유약을 더한 넓고 낮은 화분입니다.", "54000", 19),
    ("얼룩 유약 라메킨 세트 (Dappled Glaze Ramekin Set)", "오븐에서도 사용할 수 있는 얼룩 유약 라메킨 두 개입니다.", "44000", 24),
    ("직조 코튼 테이블 매트 (Woven Cotton Table Mat)", "앞뒤로 사용할 수 있는 도톰한 면 테이블 매트입니다.", "38000", 20),
    ("달빛 반지 접시 (Moonstone Ring Dish)", "반지와 작은 소지품을 담아 두는 손바닥 크기의 접시입니다.", "28000", 1),
    ("러스트 염색 쿠션 커버 (Rust-dyed Cushion Cover)", "식물의 흔적을 천에 옮기는 기법으로 한 점씩 염색했습니다.", "96000", 4),
    ("물병과 잔 세트 (Carafe and Cup Pair)", "잔을 물병 위에 포개 보관할 수 있는 침실용 세트입니다.", "82000", 13),
    ("꼬임 점토 캔들홀더 (Twisted Clay Candleholder)", "손으로 쌓아 올린 유쾌한 꼬임 실루엣의 촛대입니다.", "36000", 0),
    ("베틀 린넨 브레드 클로스 (Loom-woven Bread Cloth)", "갓 구운 빵을 따뜻하게 감싸 주는 통기성 좋은 린넨입니다.", "34000", 27),
    ("둥근 매치 스트라이커 (Rounded Match Striker)", "유약을 입힌 마찰면이 있는 촉감 좋은 세라믹 성냥 홀더입니다.", "30000", 2),
    ("내추럴 울 쿠션 커버 (Raw-edge Wool Cushion)", "자연스러운 울의 결을 살린 부드러운 쿠션 커버입니다.", "108000", 11),
    ("블루 아워 서빙 볼 (Blue Hour Serving Bowl)", "깊고 겹겹이 쌓인 푸른 유약이 시선을 끄는 큰 볼입니다.", "118000", 8),
    ("패치워크 마켓 앞치마 (Patchwork Market Apron)", "남은 린넨을 이어 만든 편안한 크로스백형 앞치마입니다.", "74000", 17),
    ("작은 봉오리 화병 세트 (Miniature Bud Vase Trio)", "서로 다른 실루엣으로 빚은 작은 화병 세 개 세트입니다.", "58000", 2),
    ("손으로 꼰 플랜트 행어 (Handwoven Plant Hanger)", "면 끈을 정성스럽게 매듭지어 만든 식물 걸이입니다.", "46000", 23),
    ("초승달 타파스 접시 (Crescent-shaped Tapas Dish)", "올리브와 견과류를 담기 좋은 초승달 모양 작은 접시입니다.", "32000", 20),
    ("천연 염색 린넨 냅킨 (Natural-dye Napkin Pair)", "식물 염색의 은은한 빛을 담은 린넨 냅킨 두 장입니다.", "40000", 5),
    ("결이 살아 있는 키친 크록 (Tall Textured Utensil Crock)", "조리 도구를 세워 두기 좋은 단단하고 질감 있는 도구통입니다.", "68000", 14),
    ("울 펠트 테이블 러너 (Wool Felt Table Runner)", "계절의 식탁에 포근함을 더하는 부드러운 울 러너입니다.", "124000", 1),
    ("손으로 깎은 차 스쿱 (Hand-carved Tea Scoop)", "찻잎을 덜어내는 작은 의식을 위해 매끄럽게 깎은 나무 스쿱입니다.", "29000", 18),
    ("뚜껑 있는 소금 단지 (Salt Cellar with Lid)", "작은 스푼과 함께 사용하는 뚜껑 달린 스톤웨어 소금 단지입니다.", "52000", 0),
]

IMAGE_URLS = [
    "https://images.unsplash.com/photo-1610701596007-11502861dcfa?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1581783342308-f792caee7e0d?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1615486364429-1f50cd4e10a8?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1596622578821-3795cebed972?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1612196808214-b7e239e5f6b7?auto=format&fit=crop&w=600&q=80",
    "https://images.unsplash.com/photo-1599643477874-5c866ea4fc1e?auto=format&fit=crop&w=600&q=80",
]

LEGACY_ARTISAN_NAMES = [
    "Ayla Demir", "Mina Park", "Theo Laurent", "Nia Okafor", "Sora Kim",
    "Luca Moretti", "Amara Diallo", "Eun Seo", "Ravi Patel", "Clara Jensen",
    "Yuki Tanaka", "Mateo Silva", "Zara Haddad", "Noah Bennett",
]

LEGACY_DROP_TITLES = [
    "Saturday Studio Drop 1",
    "Saturday Studio Drop 2",
    "Saturday Studio Drop 3",
]

LEGACY_PRODUCT_NAMES = [
    "Dune Breakfast Bowl", "Tide Espresso Cup", "Moss Serving Plate",
    "Sculpted Bud Vase", "Everyday Pourer", "Linen Table Runner",
    "Cloud Tea Cup", "Ochre Snack Plate", "Woven Market Tote",
    "Pebble Incense Holder", "Olive Oil Cruet", "Soft Grid Cushion",
    "Raku Trinket Dish", "Sage Matcha Bowl", "Natural Cotton Napkins",
    "Rustic Clay Pitcher", "Woven Wall Hanging", "Speckled Espresso Mug",
    "Hand-thrown Pasta Bowl", "Linen Bread Basket", "Terracotta Oil Lamp",
    "Riverstone Soap Dish", "Indigo Tea Towel Set", "Carved Serving Platter",
    "Sculptural Incense Burner", "Madder-dyed Linen Scarf", "Fluted Ceramic Vase",
    "Woven Coaster Set", "Hand-painted Butter Bell", "Knit Wool Throw",
    "Low Stoneware Planter", "Dappled Glaze Ramekin Set", "Woven Cotton Table Mat",
    "Moonstone Ring Dish", "Rust-dyed Cushion Cover", "Carafe and Cup Pair",
    "Twisted Clay Candleholder", "Loom-woven Bread Cloth", "Rounded Match Striker",
    "Raw-edge Wool Cushion", "Blue Hour Serving Bowl", "Patchwork Market Apron",
    "Miniature Bud Vase Trio", "Handwoven Plant Hanger",
    "Crescent-shaped Tapas Dish", "Natural-dye Napkin Pair",
    "Tall Textured Utensil Crock", "Wool Felt Table Runner",
    "Hand-carved Tea Scoop", "Salt Cellar with Lid",
]


def upcoming_saturdays(count=3):
    current_timezone = timezone.get_current_timezone()
    now = timezone.localtime()
    days_until_saturday = (5 - now.weekday()) % 7
    next_date = now.date() + timedelta(days=days_until_saturday)
    first_drop = datetime.combine(
        next_date, time(hour=19), tzinfo=current_timezone
    )
    if first_drop <= now:
        first_drop += timedelta(days=7)
    return [first_drop + timedelta(days=7 * index) for index in range(count)]


class Command(BaseCommand):
    help = "Seed CRAFTS BAPPY with Korean artisans, drops, and handmade products."

    @transaction.atomic
    def handle(self, *args, **options):
        if not (len(ARTISANS) == 14 and len(PRODUCTS) == 50 and len(IMAGE_URLS) == 8):
            raise ValueError("Seed data must contain 14 artisans, 50 products, and 8 image URLs.")

        artisans = []
        for index, (name, bio, specialty) in enumerate(ARTISANS):
            legacy = Artisan.objects.filter(name=LEGACY_ARTISAN_NAMES[index]).first()
            artisan = Artisan.objects.filter(name=name).first()
            if artisan is None and legacy is not None:
                legacy.name = name
                legacy.bio = bio
                legacy.specialty = specialty
                legacy.save()
                artisan = legacy
            else:
                artisan, _ = Artisan.objects.update_or_create(
                    name=name,
                    defaults={"bio": bio, "specialty": specialty},
                )
            artisans.append(artisan)

        drops = []
        for index, drop_datetime in enumerate(upcoming_saturdays()):
            title = f"토요일 공예 마켓 {index + 1}"
            legacy = Drop.objects.filter(title=LEGACY_DROP_TITLES[index]).first()
            drop = Drop.objects.filter(title=title).first()
            if drop is None and legacy is not None:
                legacy.title = title
                legacy.drop_datetime = drop_datetime
                legacy.is_active = index == 0
                legacy.save()
                drop = legacy
            else:
                drop, _ = Drop.objects.update_or_create(
                    title=title,
                    defaults={
                        "drop_datetime": drop_datetime,
                        "is_active": index == 0,
                    },
                )
            drops.append(drop)

        for index, (name, description, price, stock_quantity) in enumerate(PRODUCTS):
            legacy = Product.objects.filter(name=LEGACY_PRODUCT_NAMES[index]).first()
            product = Product.objects.filter(name=name).first()
            defaults = {
                "description": description,
                "price": price,
                "stock_quantity": stock_quantity,
                "drop": drops[index * len(drops) // len(PRODUCTS)],
                "artisan": artisans[index % len(artisans)],
                "image_url": IMAGE_URLS[index % len(IMAGE_URLS)],
            }
            if product is None and legacy is not None:
                legacy.name = name
                for field, value in defaults.items():
                    setattr(legacy, field, value)
                legacy.save()
            else:
                Product.objects.update_or_create(name=name, defaults=defaults)

        self.stdout.write(
            self.style.SUCCESS(
                "CRAFTS BAPPY seed complete: 14 Korean artisans, 3 upcoming drops, and 50 products."
            )
        )
