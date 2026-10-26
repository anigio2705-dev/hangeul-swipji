"""Apply reviewed teaching notes without removing units, examples or quiz slots.
The script is idempotent; review evidence lives in audit/lesson-review.json.
"""
import json
from pathlib import Path
import re
import subprocess
import hashlib

ROOT = Path(__file__).resolve().parents[1]
COURSES = ['intro','beginner1','beginner2','intermediate1','intermediate2','advanced1','advanced2']

# Notes correspond to the existing first example in units 6–50, not a rotating vocabulary item.
BEGINNER1 = '''
제는 저의의 줄임말입니다. 이름은 뒤에 자신의 이름과 이에요/예요를 말합니다.|제 means my, a contraction of 저의. After 이름은, give your name and 이에요/예요.
한국 사람은 한국 국적의 사람입니다. 사람처럼 받침이 있으면 이에요를 붙입니다.|한국 사람 means a Korean person. 사람 ends in a consonant, so add 이에요.
학생은 받침 ㅇ이 있으므로 학생이에요라고 합니다. 학생예요라고 쓰지 않습니다.|학생 ends in ㅇ: use 학생이에요, not 학생예요.
직업은 일을 뜻합니다. 회사원은 받침 ㄴ이 있으므로 회사원이에요라고 합니다.|직업 means occupation. 회사원 ends in ㄴ, so say 회사원이에요.
만나서 반가워요는 만난 사람에게 하는 인사입니다. 반갑다는 반가워요로 바뀝니다.|만나서 반가워요 is a greeting when meeting someone. 반갑다 becomes 반가워요.
명은 사람을 세는 말입니다. 넷은 명 앞에서 네로 바뀝니다: 네 명.|명 counts people. 넷 becomes 네 before a counter: 네 명, four people.
어머니 뒤의 는은 어머니를 화제로 삼습니다. 선생님은 받침이 있어 이에요를 붙입니다.|는 makes 어머니 the topic. 선생님 ends in a consonant, so add 이에요.
동생은 어린 형제나 자매를 말합니다. 동생은에서 은은 받침 뒤에 붙는 화제 조사입니다.|동생 means a younger sibling. 은 is the topic particle after a final consonant.
아버지는에서 는은 받침 없는 말 뒤에 붙습니다. 아버지는 회사원이에요는 아버지의 직업을 소개합니다.|는 follows a word without a final consonant. The sentence introduces the father's occupation.
보고 싶어요는 만나고 싶은 마음을 나타냅니다. 가족이 보고 싶어요는 가족을 그리워한다는 말입니다.|보고 싶어요 expresses wanting to see someone. 가족이 보고 싶어요 means I miss my family.
교실에는 장소를 나타내는 에를 씁니다. 학생이 있어요는 학생이 존재한다는 말입니다.|에 marks the location 교실. 학생이 있어요 says there is a student.
책상 위에는 물건보다 높은 위치입니다. 위에 책이 있어요처럼 위치 뒤에 에를 붙입니다.|책상 위 means on top of the desk. Add 에 to mark that location.
오늘 뒤에는 보통 에를 붙이지 않습니다. 숙제가 있어요는 해야 할 숙제가 있다는 뜻입니다.|Usually do not add 에 to 오늘. 숙제가 있어요 means there is homework to do.
한국어를에서 를은 공부하는 대상을 표시합니다. 공부하다의 일상 존댓말은 공부해요입니다.|를 marks what you study. 공부하다 becomes 공부해요 in everyday polite speech.
질문이 있어요는 질문하고 싶을 때 쓰는 말입니다. 질문은 받침이 있으므로 이가 붙습니다.|질문이 있어요 introduces a question. 질문 has a final consonant, so use 이.
시 앞에는 고유어 수를 씁니다. 일곱 시에에서 에는 행동이 일어나는 시간을 표시합니다.|Use native Korean numbers for hours. 에 in 일곱 시에 marks when the action happens.
세수를 하다는 얼굴을 씻는다는 뜻입니다. 아침에는 아침이라는 시간을 표시합니다.|세수를 하다 means to wash one's face. 아침에 indicates the time, in the morning.
점심을에서 을은 먹는 대상을 표시합니다. 먹다에서 다를 빼고 어요를 붙여 먹어요가 됩니다.|을 marks the object 점심. Remove 다 from 먹다 and add 어요: 먹어요.
오후에는 오후라는 시간을 나타냅니다. 일하다는 일해요로 바뀝니다.|오후에 means in the afternoon. 일하다 becomes 일해요.
열하나는 시 앞에서 열한으로 바뀝니다. 자다는 자요로 줄여 말합니다.|열하나 becomes 열한 before 시. 자다 becomes 자요.
집에는 가는 목적지를 표시합니다. 집에서와 달리 집에 가요는 집으로 이동한다는 뜻입니다.|집에 marks the destination. 집에 가요 means go home; 집에서 marks an action at home.
학교에서는 공부가 일어나는 장소입니다. 에는 목적지나 위치, 에서는 행동 장소에 주로 씁니다.|학교에서 marks where studying takes place. Contrast 에 for destination/location with 에서 for action location.
도서관에는 책이 있는 장소입니다. 많다의 일상 존댓말은 많아요입니다.|도서관에 marks the books' location. 많다 becomes 많아요, there are many.
어디는 모르는 장소를 묻습니다. 은행은 어디에 있어요?는 은행의 위치를 묻는 질문입니다.|어디 asks about an unknown place. The question asks where the bank is.
공원에서는 걷는 행동의 장소입니다. 걷다는 걸어요로 바뀌는 ㄷ 불규칙 동사입니다.|공원에서 is where walking happens. 걷다 has an irregular ㄷ form: 걸어요.
밥 뒤에는 받침이 있으므로 을을 붙입니다. 먹어요는 보통 현재 행동이나 습관을 말합니다.|밥 ends in a consonant, so add 을. 먹어요 can describe a current action or habit.
국이에서 이는 상태를 설명하는 대상을 표시합니다. 맛있어요는 음식 맛이 좋다는 뜻입니다.|이 marks the thing described. 맛있어요 means the food tastes good.
물은 마시는 대상이므로 물을이라고 합니다. 마시다는 마셔요로 줄어듭니다.|Water is what you drink, so say 물을. 마시다 contracts to 마셔요.
좋아하다 앞의 대상에는 을/를을 붙입니다. 과일은 받침이 있어 과일을이라고 합니다.|Mark the object of 좋아하다 with 을/를. 과일 ends in a consonant: 과일을.
사다는 물건을 산다는 뜻입니다. 사 + 아요는 사요가 되고, 빵은 받침이 있어 빵을이라고 합니다.|사다 means buy. 사 + 아요 contracts to 사요. Use 빵을 for the object.
날씨가의 가는 설명할 대상을 표시합니다. 맑다는 맑아요로 활용합니다.|가 marks the weather being described. 맑다 becomes 맑아요, clear.
흐리다는 흐려요로 바뀝니다. 하늘이 흐려요는 구름이 많아 하늘이 맑지 않다는 뜻입니다.|흐리다 becomes 흐려요. 하늘이 흐려요 means the sky is cloudy.
비가 와요에서 오다는 와요로 바뀝니다. 비를 와요라고 하지 않습니다.|오다 becomes 와요 in 비가 와요. Use 비가, not 비를.
눈이 와요는 눈이 내린다는 말입니다. 눈에는 받침이 있으므로 이를 붙입니다.|눈이 와요 means it is snowing. 눈 has a final consonant, so use 이.
춥다는 추워요로 바뀌는 ㅂ 불규칙 형용사입니다. 덥다도 더워요로 바뀝니다.|춥다 has an irregular ㅂ form, 추워요. Similarly 덥다 becomes 더워요.
음악을은 듣는 대상을 표시합니다. 듣다는 들어요로 바뀌는 ㄷ 불규칙 동사입니다.|음악을 marks what you listen to. 듣다 has an irregular ㄷ form: 들어요.
영화를의 를은 보는 대상을 표시합니다. 보다의 보 + 아요는 봐요로 줄어듭니다.|영화를 marks what you watch. 보 + 아요 contracts to 봐요.
매일은 날마다라는 뜻이며 보통 에를 붙이지 않습니다. 운동하다는 운동해요가 됩니다.|매일 means every day and usually takes no 에. 운동하다 becomes 운동해요.
책을은 읽는 대상입니다. 읽다에서 다를 빼고 어요를 붙이면 읽어요가 됩니다.|책을 marks what is read. Remove 다 from 읽다 and add 어요: 읽어요.
그림을 그리다는 그림을 만든다는 말입니다. 그리 + 어요는 그려요로 줄어듭니다.|그림을 그리다 means draw a picture. 그리 + 어요 contracts to 그려요.
타다 앞에는 버스를처럼 교통수단에 을/를을 붙입니다. 타 + 아요는 타요가 됩니다.|With 타다, mark the vehicle as an object: 버스를. 타 + 아요 contracts to 타요.
지하철은 받침이 있어 지하철을이라고 합니다. 지하철로 가요에서는 로가 이동 수단을 표시합니다.|지하철 ends in a consonant: 지하철을 타요. In 지하철로 가요, 로 marks transport.
택시를 불러요는 택시를 오게 요청한다는 말입니다. 부르다는 불러요로 바뀝니다.|택시를 불러요 means call a taxi. 부르다 becomes 불러요.
기차를에서 를은 기다리는 대상을 표시합니다. 기다리 + 어요는 기다려요가 됩니다.|를 marks what you wait for. 기다리 + 어요 contracts to 기다려요.
까지는 도착하는 끝 지점을 표시합니다. 걸어요는 걷다의 활용형입니다.|까지 marks the endpoint, as far as school. 걸어요 is the polite form of 걷다.
'''

BEGINNER2 = '''
두 명 자리는 두 사람이 앉는 자리입니다. 명 앞에서 둘은 두로 바뀌고, 있어요?는 자리가 있는지 묻습니다.|두 명 자리 means seats for two people. 둘 becomes 두 before 명; 있어요? asks about availability.
-지 않아요는 앞말을 부정합니다. 맵지 않아요?는 맵지 않은지 확인하는 부정 질문이므로 대답할 때 매워요/안 매워요도 함께 말합니다.|-지 않아요 negates a predicate. This negative question checks whether it is not spicy; include 매워요 or 안 매워요 to avoid an ambiguous yes/no.
뭐예요는 무엇이에요의 줄임말입니다. 추천 메뉴가 뭐예요?는 추천하는 음식을 묻습니다.|뭐예요 contracts 무엇이에요. This asks which dish is recommended.
더는 수량을 추가한다는 뜻입니다. 반찬을 더 주세요는 반찬을 추가로 요청하는 말입니다.|더 means more. 반찬을 더 주세요 requests additional side dishes.
카드로는 결제 수단을 표시합니다. -ㄹ게요는 여기서 말하는 사람의 의사를 상대에게 알립니다.|카드로 marks the payment method. -ㄹ게요 announces the speaker's intention here.
만날까요?는 함께할 행동을 제안합니다. 만나다에서 다를 빼고 ㄹ까요를 붙입니다.|만날까요? suggests doing something together. Add ㄹ까요 to the vowel-ending stem 만나-.
-아/어도 돼요?는 허락을 묻습니다. 바꾸다 → 바꿔도 돼요?는 바꾸는 것이 허용되는지 묻습니다.|-아/어도 돼요? asks permission. 바꾸다 becomes 바꿔도 돼요?, may I change it?
-(으)ㄹ 것 같아요는 확실하지 않은 예상입니다. 늦다는 늦을 것 같아요가 되고 십 분은 늦는 정도입니다.|-(으)ㄹ 것 같아요 expresses an uncertain prediction. 십 분 says how late the speaker expects to be.
도착하면은 도착하는 때를 조건으로 제시합니다. 연락할게요는 그때 연락하겠다는 약속입니다.|도착하면 sets arrival as the condition/time. 연락할게요 promises to contact the listener then.
-아/어 주세요는 정중한 요청입니다. 오다 → 와 주세요이며 조금 일찍은 요청하는 시간입니다.|-아/어 주세요 makes a polite request. 오다 becomes 와 주세요; 조금 일찍 means a little early.
여기에서의 에서는 출발점을 나타냅니다. 직진하세요는 곧장 가라는 정중한 안내입니다.|에서 marks the starting point here. 직진하세요 politely tells someone to go straight.
사거리에서는 방향을 바꾸는 장소입니다. 왼쪽으로의 으로는 이동 방향을 표시합니다.|사거리에서 marks where to turn. 으로 in 왼쪽으로 marks direction.
길을은 건너는 대상입니다. 건너다에 세요를 붙이면 건너세요가 됩니다.|길을 marks what is crossed. Add 세요 to 건너-: 건너세요.
여기에서는 거리를 재는 기준점입니다. 가깝다는 가까워요로 바뀝니다.|여기에서 marks the reference point for distance. 가깝다 becomes 가까워요.
오른쪽에는 약국의 위치입니다. 약국은 받침이 있으므로 약국이 있어요라고 합니다.|오른쪽에 marks location. 약국 has a final consonant, so say 약국이 있어요.
얼마예요?는 가격을 묻습니다. 이거는 이것의 말하기 표현입니다.|얼마예요? asks the price. 이거 is the conversational form of 이것.
도는 추가를 나타냅니다. 다른 색깔도 있어요?는 현재 색 외에 다른 색의 상품도 있는지 묻습니다.|도 means also. This asks whether another color is available too.
더는 비교 정도를 나타냅니다. 크다 → 큰이 사이즈를 꾸며 더 큰 사이즈라고 합니다.|더 marks a comparison. 크다 becomes the noun modifier 큰: 더 큰 사이즈, a larger size.
-(으)ㄹ 수 있어요?는 가능 여부를 묻습니다. 교환하다 → 교환할 수 있어요?입니다.|-(으)ㄹ 수 있어요? asks whether something is possible. 교환하다 becomes 교환할 수 있어요?.
영수증은 받침이 있으므로 을을 붙입니다. 주세요는 물건을 정중히 요청하는 말입니다.|영수증 ends in a consonant, so add 을. 주세요 politely requests an item.
아프다는 아파요로 바뀝니다. 머리가 아파요는 머리에 통증이 있다는 증상 표현입니다.|아프다 becomes 아파요. 머리가 아파요 describes a headache.
부터는 시작 시점을 표시합니다. 어제부터 기침이 나요는 기침이 어제 시작해 이어진다는 말입니다.|부터 marks a starting time. This says the cough began yesterday and continues.
열이 있어요는 몸에 열이 난다는 말입니다. 좀은 조금의 줄임말로 정도를 부드럽게 표현합니다.|열이 있어요 describes having a fever. 좀 is short for 조금 and softens the description.
-아/어야 해요는 필요나 의무를 나타냅니다. 먹다 → 먹어야 해요입니다.|-아/어야 해요 expresses necessity: 먹다 → 먹어야 해요.
-(으)려고 해요는 의도를 말합니다. 가다 → 가려고 해요이며 병원에는 목적지입니다.|-(으)려고 해요 expresses intention. 가다 becomes 가려고 해요; 병원에 marks destination.
보여 주세요는 보다의 명령이 아니라 보여 주다의 요청형입니다. 상대에게 여권을 제시해 달라고 합니다.|보여 주세요 requests showing something, from 보여 주다. It asks the listener to present a passport.
예약했어요는 예약하다의 과거형입니다. 표를은 예약한 대상을 표시합니다.|예약했어요 is the past of 예약하다. 표를 marks what was booked.
곧은 가까운 미래를 나타냅니다. 출발해요는 출발하다의 일상 존댓말입니다.|곧 means soon. 출발해요 is the everyday polite form of 출발하다.
호텔에는 도착 지점을 표시합니다. 도착했어요는 도착하다의 과거형입니다.|호텔에 marks the arrival point. 도착했어요 is the past of 도착하다.
맡기다는 다른 사람에게 보관을 부탁한다는 뜻입니다. 맡길 수 있어요?는 보관 가능 여부를 묻습니다.|맡기다 means entrust something for safekeeping. 맡길 수 있어요? asks whether leaving it is possible.
-아/어 봤어요는 경험을 말합니다. 가다 → 가 봤어요는 실제로 가 본 경험입니다.|-아/어 봤어요 expresses experience. 가 봤어요 means having visited.
먹어 봤어요는 먹은 경험이 있다는 말입니다. 단순 과거 먹었어요와 달리 경험을 강조합니다.|먹어 봤어요 emphasizes having tried food, unlike the simple past 먹었어요.
작년에는 지난 해의 시간을 나타냅니다. 배우다 → 배웠어요는 과거의 배움을 말합니다.|작년에 means last year. 배우다 becomes 배웠어요 for a past learning event.
-(으)ㄴ 적이 있어요는 과거 경험을 말합니다. 만나다 → 만난 적이 있어요입니다.|-(으)ㄴ 적이 있어요 expresses past experience. 만나다 becomes 만난 적이 있어요.
처음으로는 첫 경험임을 강조합니다. 만들다 → 만들었어요는 과거형입니다.|처음으로 emphasizes a first experience. 만들었어요 is the past of 만들다.
조용한은 조용하다가 명사를 꾸미는 형태입니다. 조용한 곳을은 좋아하는 대상을 표시합니다.|조용한 modifies a noun, from 조용하다. 조용한 곳을 is the object of 좋아해요.
사람이 많은은 곳을 꾸미는 절입니다. 싫어요는 좋아하지 않는 상태를 말합니다.|사람이 많은 is a clause modifying 곳. 싫어요 expresses dislike.
보다 앞에는 비교 기준을 놓습니다. 커피보다 차를 더 좋아해요는 차를 더 선호한다는 말입니다.|Place the comparison standard before 보다. This says the speaker prefers tea to coffee.
더 편해요는 다른 대상과 비교해 편안함의 정도가 크다는 말입니다. 편하다 → 편해요입니다.|더 편해요 means more comfortable in a comparison. 편하다 becomes 편해요.
-고 싶어요는 말하는 사람의 바람을 나타냅니다. 쉬다 → 쉬고 싶어요입니다.|-고 싶어요 expresses the speaker's wish. 쉬다 becomes 쉬고 싶어요.
청소해야 해요는 청소할 필요나 의무입니다. 청소하고 싶어요는 바람이므로 뜻이 다릅니다.|청소해야 해요 expresses necessity. Contrast 청소하고 싶어요, a wish.
-고 있어요는 진행 중인 행동을 말합니다. 하다 → 하고 있어요입니다.|-고 있어요 describes an action in progress. 하다 becomes 하고 있어요.
만들고 있어요는 지금 만드는 중이라는 말입니다. 만들었어요는 이미 끝난 과거이므로 다릅니다.|만들고 있어요 describes making something now. Contrast 만들었어요, a completed past action.
정리해 주세요는 상대에게 정리를 부탁합니다. 정리했어요는 과거 사실이므로 요청이 아닙니다.|정리해 주세요 asks the listener to organize. 정리했어요 reports a past action instead.
고장 난은 의자를 꾸미고, 고쳤어요는 고치다의 과거형입니다. 고친 대상은 의자입니다.|고장 난 modifies 의자. 고쳤어요 is the past of 고치다; the chair is the object repaired.
'''

# Ordered from specific constructions to broad endings. Each rule includes a contrast example.
RULES = [
 (r'못 먹었어요', '못은 능력이나 상황 때문에 할 수 없음을 나타냅니다. 안은 보통 의도적으로 하지 않음을 나타냅니다. 먹었어요는 과거입니다.', '못 expresses inability or circumstantial prevention; 안 usually expresses not doing something. 먹었어요 is past tense.', '못 먹었어요. / 안 먹었어요.', 'I could not eat it. / I did not eat it.'),
 (r'합시다', '-(으)ㅂ시다는 함께할 행동을 제안하는 격식 표현입니다. 받침이 없는 정리하-에는 ㅂ시다를 붙입니다.', '-(으)ㅂ시다 formally proposes a joint action. Add ㅂ시다 to vowel-ending 정리하-.', '정리합시다.', 'Let us organize it.'),
 (r'보여 줍니다', '보여 주다는 상대가 볼 수 있게 한다는 뜻입니다. 이 문장에서는 도표가 추세를 나타낸다는 의미입니다.', '보여 주다 means show. Here the chart displays a trend for the reader.', '자료가 변화를 보여 줍니다.', 'The data show a change.'),
 (r'되어야 합니다|밝혀야 합니다', '-아/어야 하다는 필요나 의무입니다. 제시되어야는 피동 제시되다의 필요, 밝혀야는 밝히다의 필요입니다.', '-아/어야 하다 expresses necessity. 제시되어야 is passive, must be presented; 밝혀야 is active, must clarify.', '근거가 제시되어야 합니다.', 'Evidence must be presented.'),

 (r'참이어도', '양보 -아/어도는 앞 조건을 인정해도 뒤 결론이 달라질 수 있음을 말합니다. 전제가 참이고 추론 형식도 타당하면 결론은 참입니다. 이 예문은 전제만 참이라고 결론까지 보장되지는 않는다는 뜻입니다.', 'Concession -아/어도 means even if. True premises plus valid reasoning guarantee a true conclusion; true premises alone do not.', '비가 와도 가요. / 비가 오면 안 가요.', 'I go even if it rains. / If it rains, I do not go.'),
 (r'일반화하기는|도출하기는|내리기는', '-기는은 동작을 화제로 삼아 대조하거나 제한합니다. 어렵다는 불가능하다는 단정과 다릅니다.', '-기는 topicalizes an action, often with contrast or limitation. Difficult does not mean impossible.', '읽기는 쉬워요. / 쓰기는 어려워요.', 'Reading is easy. / Writing is difficult.'),
 (r'해서는 안|혼동해서는', '-아/어서는 안 되다는 금지나 부적절함을 나타냅니다. -지 않아도 되다는 하지 않아도 된다는 허용이므로 다릅니다.', '-아/어서는 안 되다 expresses prohibition. Contrast -지 않아도 되다, not having to do something.', '잊어서는 안 됩니다. / 쓰지 않아도 됩니다.', 'You must not forget. / You do not have to write.'),
 (r'기 전에', '-기 전에 앞에는 동사 어간을 놓아 먼저 할 일과 뒤의 일을 구분합니다.', 'Verb stem + 기 전에 means before doing that action. Track which action comes first.', '먹기 전에 손을 씻어요.', 'I wash my hands before eating.'),
 (r'수는 없|못할 수도', '-(으)ㄹ 수 없다의 는은 대조·강조를 더합니다. 못할 수도 있다는 불가능할 가능성이 있다는 뜻입니다.', '-(으)ㄹ 수 없다 expresses inability; 는 adds contrast/emphasis. 못할 수도 있다 expresses possible inability.', '갈 수 있어요. / 갈 수는 없어요.', 'I can go. / Going is not possible for me.'),
 (r'수 있습니다|수 있어요', '-(으)ㄹ 수 있다 앞에는 동사 어간을 씁니다. 문맥에 따라 능력이나 가능성을 나타내며 실제로 일어났다는 뜻은 아닙니다.', 'Verb stem + (으)ㄹ 수 있다 expresses ability or possibility, not proof that the event occurred.', '갈 수 있어요. / 갔어요.', 'I can go. / I went.'),
 (r'수도 있', '-(으)ㄹ 수도 있다의 도는 여러 가능성 중 하나임을 나타냅니다. 반드시 일어난다는 단정과 구분합니다.', '-(으)ㄹ 수도 있다 marks one possible outcome. It is not a statement of certainty.', '비가 올 수도 있어요. / 비가 와요.', 'It might rain. / It is raining.'),
 (r'필요가 있습니다|필요합니다|필요해요', '동사 뒤의 -(으)ㄹ 필요가 있다는 행동의 필요성을 말합니다. 명사 뒤의 이/가 필요하다는 필요한 대상을 말합니다.', 'Verb + (으)ㄹ 필요가 있다 expresses a needed action. Noun + 이/가 필요하다 names what is needed.', '확인할 필요가 있어요. / 자료가 필요해요.', 'We need to check. / We need materials.'),
 (r'주시기 바랍니다', '-아/어 주시기 바랍니다는 상대에게 행동을 요청하는 격식 표현입니다. -시-는 높임을 더합니다.', '-아/어 주시기 바랍니다 is a formal request; -시- adds honorific respect.', '확인해 주세요. / 확인해 주시기 바랍니다.', 'Please check. / Please check (formal).'),
 (r'주십시오', '-아/어 주십시오는 격식 있는 정중한 요청입니다. 친구 사이의 해 줘와 말투가 다릅니다.', '-아/어 주십시오 is a formal polite request, unlike casual 해 줘.', '읽어 주세요. / 읽어 주십시오.', 'Please read. / Please read (formal).'),
 (r'주셔서', '-아/어 주셔서는 상대의 도움에 대한 감사 이유를 나타냅니다. 주다에 높임 -시-와 이유 -어서가 연결됩니다.', '-아/어 주셔서 gives the reason for thanks, combining benefactive 주다, honorific 시, and causal 어서.', '도와주셔서 감사합니다.', 'Thank you for helping me.'),
 (r'안내드립니다|감사드립니다', '드리다는 주다보다 자신을 낮추어 상대를 높이는 표현입니다. 안내드립니다는 안내하다의 격식 있는 표현입니다.', '드리다 humbles the speaker toward the addressee. 안내드립니다 is a formal way to give information.', '감사해요. / 감사드립니다.', 'Thank you. / Thank you (deferential).'),
 (r'구합니다', '양해를 구하다는 상대가 사정을 이해해 주기를 요청한다는 뜻입니다. 구하다는 여기서 요청하다는 뜻이며 구입하다가 아닙니다.', '양해를 구하다 requests understanding. 구하다 here means seek/request, not buy.', '양해를 구합니다. / 동의를 구합니다.', 'We ask for your understanding. / We seek consent.'),
 (r'고 있습니다|고 있어요', '-고 있다는 진행 중인 행동이나 계속되는 상태를 나타냅니다. 명사+중이다와도 비교할 수 있습니다.', '-고 있다 describes an ongoing action or continuing state. Compare noun + 중이다, in progress.', '변하고 있어요. / 변했어요.', 'It is changing. / It changed.'),
 (r'지 않았|되지 않|뜻하지 않', '-지 않다는 앞의 동작이나 상태를 부정합니다. 아직 -지 않았다는 현재까지 완료되지 않았음을 말합니다.', '-지 않다 negates a predicate. 아직 -지 않았다 means not completed yet.', '확인됐어요. / 아직 확인되지 않았어요.', 'It was verified. / It has not been verified yet.'),
 (r'되었습니다|됩니다|됐습니다|연결됩니다', '명사+되다는 상태 변화나 피동을 나타낼 수 있습니다. 시행됩니다는 제도가 시행을 받는 쪽임을 나타내며 시행합니다와 초점이 다릅니다.', 'Noun + 되다 can express change or passive voice. 시행됩니다 and 시행합니다 differ in focus (undergoer versus actor), not inherently in time.', '결과를 공개했습니다. / 결과가 공개됐습니다.', 'They released the results. / The results were released.'),
 (r'해졌|커지|깊어집', '-아/어지다는 상태의 변화를 나타냅니다. 원래부터 그 상태였다는 뜻과 구분합니다.', '-아/어지다 expresses a change of state, unlike simply describing an existing state.', '편해요. / 편해졌어요.', 'It is comfortable. / It has become comfortable.'),
 (r'할수록', '-(으)ㄹ수록은 앞의 변화가 커질 때 뒤의 정도도 함께 변함을 나타냅니다.', '-(으)ㄹ수록 links increasing degree in one situation to a change in another: the more …, the more ….', '읽을수록 재미있어요.', 'The more I read, the more interesting it is.'),
 (r'적이 있', '-(으)ㄴ 적이 있다는 과거 경험을 나타냅니다. 동작의 횟수를 반드시 한 번으로 제한하지 않습니다.', '-(으)ㄴ 적이 있다 expresses past experience without necessarily limiting it to once.', '만난 적이 있어요. / 만나고 있어요.', 'I have met them before. / I am meeting them now.'),
 (r'보세요', '-아/어 보세요는 시도를 권하는 정중한 말입니다. 보다는 여기서 눈으로 본다는 뜻이 아닙니다.', '-아/어 보세요 politely suggests trying an action. 보다 here does not mean visually seeing.', '읽어 보세요.', 'Try reading it.'),
 (r'덕분에', '명사+덕분에는 좋은 결과의 원인이나 도움을 나타냅니다. 부정적인 원인을 말하는 때문에와 구분해 씁니다.', 'Noun + 덕분에 gives a helpful cause, thanks to. 때문에 is a more general causal expression.', '친구 덕분에 끝냈어요.', 'I finished thanks to a friend.'),
 (r'반면', '-(으)ㄴ/는 반면은 두 특징을 대조합니다. 앞과 뒤에서 무엇을 같은 기준으로 비교하는지 확인합니다.', '-(으)ㄴ/는 반면 contrasts two features. Identify a shared comparison dimension.', '값은 싼 반면 크기는 작아요.', 'It is inexpensive, whereas its size is small.'),
 (r'지만', '-지만은 앞의 사실을 인정하면서 대조되는 내용을 연결합니다. 이유를 나타내는 -아서/어서와 구분합니다.', '-지만 connects contrasting information, unlike causal -아서/어서.', '비싸지만 샀어요.', 'It was expensive, but I bought it.'),
 (r'으면|하면|오면|나면', '-(으)면은 조건이나 아직 일어나지 않은 때를 나타냅니다. 받침이 있으면 보통 으면, 없으면 면을 붙입니다.', '-(으)면 marks a condition or future occasion. Usually use 으면 after a consonant and 면 after a vowel.', '시간이 있으면 만나요.', 'Let us meet if you have time.'),
 (r'싶어요', '동사 어간+-고 싶다는 바람을 나타냅니다. 목적이 확정되었다는 말과는 다릅니다.', 'Verb stem + 고 싶다 expresses a wish, not a confirmed arrangement.', '가고 싶어요. / 갈 예정이에요.', 'I want to go. / I am scheduled to go.'),
 (r'려고 해요', '-(으)려고 하다는 의도나 계획을 나타냅니다. 이미 끝난 일에 쓰는 과거형과 구분합니다.', '-(으)려고 하다 expresses an intention or plan, unlike a completed past action.', '가려고 해요. / 갔어요.', 'I plan to go. / I went.'),
 (r'예정이에요|거예요', '-(으)ㄹ 예정이다는 예정, -(으)ㄹ 거예요는 문맥에 따라 계획이나 예상을 나타냅니다.', '-(으)ㄹ 예정이다 expresses an arrangement; -(으)ㄹ 거예요 expresses a plan or prediction depending on context.', '내일 갈 예정이에요.', 'I am scheduled to go tomorrow.'),
 (r'다고 했|다고 들|다고 대답', '평서문을 전할 때 동사 현재는 -ㄴ/는다고, 형용사는 -다고를 씁니다. 인용한 내용과 전달한 사람을 나누어 읽습니다.', 'For reported statements use ㄴ/는다고 with present action verbs and 다고 with adjectives. Separate the reported message from its speaker.', '온다고 했어요. / 좋다고 했어요.', 'They said they would come. / They said it was good.'),
 (r'하라고', '-(으)라고 하다는 명령·요청을 간접 전달합니다. 평서문 전달 -다고 하다와 구분합니다.', '-(으)라고 하다 reports a command or request, unlike a reported statement with -다고 하다.', '읽으라고 했어요.', 'They told me to read.'),
 (r'냐고', '-냐고 묻다는 질문을 간접 전달합니다. 원래 질문과 질문하는 행동을 구분합니다.', '-냐고 묻다 reports a question. Identify the original question separately from the act of asking.', '어디에 가냐고 물었어요.', 'They asked where I was going.'),
 (r'먼저|그다음에|마지막으로', '먼저·그다음에·마지막으로는 순서를 나타냅니다. 같은 일을 반복하는 대신 각 단계의 행동을 구분합니다.', '먼저, 그다음에 and 마지막으로 mark first, next and finally. Identify the action at each step.', '먼저 읽고 그다음에 써요.', 'First read, then write.'),
 (r'^하지만|^그래서', '하지만은 대조, 그래서는 결과를 이어 줍니다. 앞 문장의 내용과 뒤 문장이 어떤 관계인지 먼저 확인합니다.', '하지만 introduces contrast; 그래서 introduces a result. Read the preceding context to identify the relationship.', '비가 와요. 그래서 집에 있어요.', 'It is raining. So I am staying home.'),
 (r'보다', '명사+보다는 비교의 기준입니다. 두 대상과 비교하는 성질을 나누어 읽습니다.', 'Noun + 보다 marks the comparison standard. Identify both items and the compared property.', '차보다 물이 더 싸요.', 'Water is cheaper than tea.'),
 (r'서 .*었어요|서 .*했어요', '-아서/어서가 이유일 때는 앞이 원인, 뒤가 결과입니다. 하다 → 해서, 오다 → 와서처럼 활용합니다.', 'With causal -아서/어서, the first clause gives the cause and the second the result. 하다 → 해서; 오다 → 와서.', '피곤해서 쉬었어요.', 'I rested because I was tired.'),
 (r'위해', '명사+을/를 위해는 목적이나 이익의 대상을 나타냅니다. 동사는 -기 위해로 바꿉니다.', 'Noun + 을/를 위해 marks purpose or benefit. Use verb + 기 위해 with an action.', '시험을 위해 공부해요.', 'I study for the exam.'),
 (r'좋겠어요', '-는 게 좋겠어요는 행동을 부드럽게 권하거나 평가합니다. 반드시 해야 한다는 강한 의무와 다릅니다.', '-는 게 좋겠어요 softly recommends an action, rather than imposing a strict obligation.', '쉬는 게 좋겠어요.', 'It would be good to rest.'),
 (r'봅시다', '-아/어 봅시다는 함께 시도하자는 제안입니다. 격식 있는 말투이며 개인의 미래 약속과 구분합니다.', '-아/어 봅시다 proposes trying something together in a formal style, not a personal future promise.', '다른 방법을 찾아봅시다.', 'Let us try finding another method.'),
 (r'해야 합니다|펴야 합니다|봐야 합니다|들어야 합니다|남겨야 합니다|두어야 합니다', '-아/어야 하다는 의무나 필요를 나타냅니다. 격식체 합니다가 붙어 의견을 공식적으로 제시합니다. 사실이 이미 이루어졌다는 뜻은 아닙니다.', '-아/어야 하다 expresses necessity or obligation. 합니다 makes the style formal; the action has not thereby already happened.', '검토해야 합니다. / 검토했습니다.', 'We must review it. / We reviewed it.'),
 (r'겠습니다', '-겠습니다는 여기서 발표자의 의도·약속을 나타냅니다. 문맥에 따라 추측도 가능하지만 이 발표 예문에서는 앞으로 할 행동입니다.', '-겠습니다 expresses the presenter\'s intention here. It can express inference elsewhere, but here announces an upcoming action.', '비교하겠습니다. / 비교했습니다.', 'I will compare. / I compared.'),
 (r'마다', '명사+마다는 각 대상이나 반복되는 단위를 나타냅니다. 모두가 동일하다는 뜻이 아니라 각각을 가리킵니다.', 'Noun + 마다 refers to each item or repeated unit, not necessarily to identical characteristics.', '사람마다 생각이 달라요.', 'People have different ideas.'),
 (r'에 따라', '명사+에 따라는 기준이나 변화에 대응하는 관계를 나타냅니다. 뒤에는 그에 맞게 달라지는 내용을 둡니다.', 'Noun + 에 따라 marks dependence on a standard or changing factor; identify what changes with it.', '시간에 따라 색이 달라요.', 'The color varies with time.'),
 (r'달려 있습니다', '명사+에 달려 있다는 결과가 그 조건에 의존한다는 뜻입니다. 달리다의 달려요와 문맥이 다릅니다.', 'Noun + 에 달려 있다 means depend on that condition. It differs in meaning from running.', '성공은 준비에 달려 있습니다.', 'Success depends on preparation.'),
 (r'기능을 합니다|상징합니다|암시합니다|드러냅니다|강조합니다|뜻하지', '주어가 어떤 의미나 역할을 갖는지 설명하는 문장입니다. 상징은 직접 뜻하는 대상 너머의 의미, 암시는 직접 말하지 않고 넌지시 나타내는 것입니다.', 'This describes a subject\'s meaning or function. A symbol represents a further meaning; implication suggests something indirectly.', '침묵이 갈등을 암시합니다.', 'Silence suggests conflict.'),
 (r'어렵습니다|쉽지 않습니다', '동작+-기는 어렵다/쉽지 않다는 그 동작에 대한 평가입니다. 완전히 불가능하다고 단정하지 않습니다.', 'Action + 기는 어렵다/쉽지 않다 evaluates difficulty without asserting absolute impossibility.', '판단하기는 어렵습니다.', 'It is difficult to judge.'),
 (r'있습니다|존재합니다', '있다/존재하다는 대상이나 상태의 존재를 말합니다. 에는은 존재하는 영역을 화제로 삼고, 이/가는 존재하는 대상을 표시합니다.', '있다/존재하다 states existence. 에는 marks the domain as topic; 이/가 marks what exists.', '이 주장에는 한계가 있습니다.', 'This claim has limitations.'),
 (r'다릅니다', '명사+와/과 다르다는 두 대상을 비교해 차이가 있음을 말합니다. 간은 집단 사이의 관계를 나타냅니다.', 'Noun + 와/과 다르다 expresses difference between two things. 간 refers to a relation between groups.', '계획은 결과와 다릅니다.', 'The plan differs from the result.'),
 (r'중요합니다|원칙입니다', '동사+-는 것은 동작을 명사처럼 만들어 평가합니다. 명사+이다는 대상을 어떤 개념으로 분류하거나 설명합니다.', 'Verb + 는 것 turns an action into a noun phrase for evaluation. Noun + 이다 identifies or describes.', '확인하는 것이 중요합니다.', 'Checking is important.'),
 (r'했습니다|갔어요|봤어요|했어요|입었어요|탔어요', '-았/었-은 과거를 나타냅니다. 목적어의 을/를과 주어의 이/가를 구분해 누가 무엇을 했는지 찾습니다.', '-았/었- marks past time. Use object 을/를 and subject 이/가 to identify who did what.', '자료를 확인했습니다.', 'We checked the materials.'),
 (r'동의해요|생각해요|좋아요', '의견을 말할 때 제 생각에는으로 관점을 밝힐 수 있습니다. 의견에 동의하다는 같은 생각임을, 다르게 생각하다는 차이를 나타냅니다.', '제 생각에는 introduces a viewpoint. 의견에 동의하다 expresses agreement; 다르게 생각하다 expresses a different view.', '저는 다르게 생각해요.', 'I think differently.'),
 (r'늘어요|달라요', '상태나 변화를 나타내는 일상 존댓말입니다. 다르다는 달라요로, 늘다는 늘어요로 활용합니다.', 'These polite predicates describe a state or change. 다르다 becomes 달라요; 늘다 becomes 늘어요.', '두 방법은 달라요.', 'The two methods are different.'),
 (r'나타납니다|보입니다|높입니다|뒷받침합니다', '서술어 앞의 이/가는 주어, 을/를은 목적어입니다. 나타나다는 드러나는 현상, 높이다는 대상을 더 높게 만드는 행동을 말합니다.', '이/가 marks the subject; 을/를 marks the object. 나타나다 describes emergence; 높이다 is raising something.', '차이가 나타납니다. / 신뢰를 높입니다.', 'A difference emerges. / It increases trust.'),
]

def parse_notes(s):
    return [line.split('|') for line in s.strip().splitlines()]

def replace_strings(x, old, new):
    if isinstance(x,str): return x.replace(old,new)
    if isinstance(x,list): return [replace_strings(v,old,new) for v in x]
    if isinstance(x,dict): return {k:replace_strings(v,old,new) for k,v in x.items()}
    return x

def main():
    evidence=[]; unmatched=[]
    for course in COURSES:
        file=ROOT/(course+'.html'); source=file.read_text(); m=re.search(r'const units=(\[.*?\]);',source,re.S); units=json.loads(m[1]); before=json.loads(re.search(r'const units=(\[.*?\]);',subprocess.check_output(['git','show','46745d28b17554f7d0f67e3e5515778b7ccb35e3:'+course+'.html'],cwd=ROOT,text=True),re.S)[1])
        # Semantic and naturalness corrections are applied to matching prompts/options too.
        fixes=[('서울은 부산보다 커요.','이 가방은 저 가방보다 커요.'),('Seoul is larger than Busan.','This bag is larger than that bag.'),('반증 가능성을 고려해야 합니다.','반증 가능성을 고려해야 합니다.'),('We should consider counterevidence.','We should consider falsifiability.'),('검증되지 않은 주장은 확산을 경계해야 합니다.','검증되지 않은 주장의 확산을 경계해야 합니다.'),('We apologize for the inconvenience.','We ask for your understanding regarding the inconvenience.'),('I wake up at seven.','I wake up at seven in the morning.'),('I go to bed at eleven.','I go to bed at eleven at night.')]
        applied=[]
        for old,new in fixes:
            if old!=new and old in json.dumps(units,ensure_ascii=False): units=replace_strings(units,old,new);applied.append([old,new])
        for i,u in enumerate(units):
            # The suffix follows the quoted Korean word's final sound, not the quote mark.
            if course=='intro':
                for q in u['quiz']:
                    q[0]=q[0].replace('‘안녕’는','‘안녕’은').replace('‘화장실’는','‘화장실’은').replace('‘병원’는','‘병원’은')
            if course=='beginner1' and i==3:
                u['quiz'][3][0]="'학교에 가요'에서 목적지를 나타내는 조사는?"
                u['quiz'][3][1]='Which particle marks the destination in 학교에 가요?'
            if course=='beginner2' and i==2:
                u['quiz'][1][0]="'버스___ 가요.'에서 교통수단을 나타내는 조사는?"
                u['quiz'][1][1]='Which particle means by bus in 버스___ 가요?'
            first=u['sent'][0]
            if i>=5 and course in ['beginner1','beginner2']:
                u['title'][0]=u['title'][0].split(' · ')[0]+' · '+first[0]
            if i>=5 and course in ['beginner1','beginner2']:
                notes=parse_notes(BEGINNER1 if course=='beginner1' else BEGINNER2)
                assert len(notes)==45
                u['grammar']=[notes[i-5],first]
            elif i>=5 and course!='intro':
                found=next((r for r in RULES if re.search(r[0],first[0])),None)
                if not found:
                    unmatched.append([course,i+1,first[0]])
                else:u['grammar']=[[found[1],found[2]],first,[found[3],found[4]]]
            # A worked retrieval task gives independent learners a checkable model.
            if course!='intro':
                model=u['sent'][1]
                task=['혼자 연습: 해석만 보고 다음 문장을 말한 뒤 원문과 비교하세요. '+model[1]+' → '+model[0], 'Self-check: cover the Korean, say this from its meaning, then compare. '+model[1]+' → '+model[0]]
                if task not in u['grammar']:u['grammar'].append(task)
            # Explicitly teach family terms that English alone does not disambiguate.
            for pair in u['v']:
                if pair==['언니','older sister']:pair[1]='older sister (female speaker)'
                if pair==['형','older brother']:pair[1]='older brother (male speaker)'
            for q in u['quiz']:
                q[0]=q[0].replace('older sister (female speaker)','older sister').replace('older brother (male speaker)','older brother')
                if q[0].startswith('이 단원의 중심 표현은?'):
                    q[0]=q[0].replace('older sister','older sister (female speaker)').replace('older brother','older brother (male speaker)')
                q[2]=[{'older sister':'older sister (female speaker)','older brother':'older brother (male speaker)'}.get(option,option) for option in q[2]]
            # Existing items were literal duplicates; replace just their slot with a transfer check.
            if course=='beginner2' and i==3:u['quiz'][3]=['어제 여행이 재미있___. 과거형으로 완성하세요.','Complete the past-tense sentence.', ['어요','었어요','을 거예요','으세요'],1]
            if course=='beginner2' and i==4:u['quiz'][3]=['물건을 바꾸기 전에 가능 여부를 묻는 말은?','Which asks whether an exchange is possible?', ['바꿨어요.','바꿀 수 있어요?','바꿀 거예요.','바꾸지 마세요.'],1]
            # Sort by content-derived hashes so repeated runs are stable and keys move with answers.
            for qi,q in enumerate(u['quiz']):
                answer=q[2][q[3]]
                q[2]=sorted(q[2],key=lambda option:hashlib.sha256((course+':'+str(i+1)+':'+str(qi+1)+':'+option).encode()).hexdigest())
                q[3]=q[2].index(answer)
            evidence.append({'course':course,'unit':i+1,'title':u['title'][0],'examples':len(u['sent']),'vocabulary':len(u['v']),'questions':len(u['quiz']),'teachingNotesChanged':before[i]['grammar']!=u['grammar'],'contentChanged':before[i]!=u,'changedFields':[key for key in u if before[i].get(key)!=u[key]],'review':'AI linguistic review of shared source pairs and unit application; no learner trial','corrections':[[a,b] for a,b in fixes if a!=b and a in json.dumps(before[i],ensure_ascii=False)]})
        assert len(units)==50 and sum(len(x['quiz']) for x in units)==(258 if course=='intro' else 250)
        file.write_text(source[:m.start(1)]+json.dumps(units,ensure_ascii=False,separators=(',',':'))+source[m.end(1):])
    if unmatched:raise RuntimeError('No teaching rule selected: '+json.dumps(unmatched,ensure_ascii=False))
    (ROOT/'audit').mkdir(exist_ok=True)
    (ROOT/'audit/lesson-review.json').write_text(json.dumps({'scope':'AI source-content review, separate from structural checks and learner validation','units':evidence},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reviewed':len(evidence),'changed':sum(x['contentChanged'] for x in evidence)},ensure_ascii=False))

if __name__=='__main__':main()
