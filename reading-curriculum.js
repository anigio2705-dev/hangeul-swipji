/* Graded rereading: 20 shared situations × 2 tasks × 15 levels.
 * Sentence pairs are authored together. This is not 600 independent stories.
 * Previous source passages remain available through legacyContent().
 */
(() => {
 'use strict';
 // Each row: basic three sentences; development four; analysis four; limits three.
 // The original seed's three sentences are inserted after the basic sentences.
 const rows = [
 `아침이에요.|It is morning.
 저는 일어나요.|I get up.
 창문을 열어요.|I open the window.
 창문 밖에서 새가 울어서 잠깐 귀를 기울였습니다.|A bird was singing outside, so I listened for a moment.
 평소에는 서둘러 나가지만 오늘은 방을 먼저 정리했습니다.|I usually leave in a hurry, but today I tidied my room first.
 정리를 끝낸 뒤 오늘 배울 내용을 공책에 적었습니다.|After tidying up, I wrote in my notebook what I would learn today.
 작은 일을 먼저 끝내니 공부를 시작하기가 수월했습니다.|Finishing a small task first made it easier to begin studying.
 아침 습관을 바꾼 목적은 많은 일을 한꺼번에 처리하는 것이 아니었습니다.|The purpose of changing my morning routine was not to do many things at once.
 해야 할 일을 구체적으로 적으면 막연한 부담을 줄일 수 있다고 생각했습니다.|I thought listing specific tasks could reduce a vague sense of pressure.
 다만 오늘 집중이 잘된 이유가 정리 때문인지는 확인하지 못했습니다.|However, I could not establish whether tidying up caused today's good concentration.
 충분히 잔 것도 집중에 영향을 주었을 수 있기 때문입니다.|Getting enough sleep may also have affected my concentration.
 이 경험만으로 모든 사람에게 같은 아침 습관을 권하기는 어렵습니다.|This experience alone is insufficient to recommend the same routine to everyone.
 습관의 효과를 살피려면 수면 시간처럼 다른 조건도 함께 기록해야 합니다.|To examine its effect, other conditions such as sleep duration must also be recorded.
 따라서 내일도 같은 방법을 시도하되 결과를 미리 단정하지 않기로 했습니다.|I therefore decided to try it again tomorrow without assuming the result.`,
 `여기는 도서관이에요.|This is a library.
 저는 책을 골라요.|I choose a book.
 의자에 앉아요.|I sit on a chair.
 책을 읽다가 모르는 말이 나와서 앞 문장을 다시 읽었습니다.|An unfamiliar word appeared, so I reread the preceding sentence.
 먼저 뜻을 짐작한 뒤 사전에서 실제 뜻을 확인했습니다.|I first guessed its meaning and then checked a dictionary.
 뜻을 안다고 생각했던 말도 문장 안에서는 다르게 쓰였습니다.|Even a word I thought I knew was used differently in context.
 저는 새 단어와 함께 그 단어가 나온 문장도 적었습니다.|I wrote down both the new word and the sentence containing it.
 단어만 외우는 방법과 문맥 속에서 익히는 방법은 서로 보완할 수 있습니다.|Memorizing words and learning them in context can complement each other.
 문맥은 뜻을 짐작하게 하지만 언제나 정답을 알려 주는 것은 아닙니다.|Context helps us infer meanings but does not always reveal the correct one.
 사전에서 찾은 첫 번째 뜻이 해당 문장에 맞는지도 검토해야 합니다.|We must also check whether the first dictionary meaning fits the sentence.
 이런 확인 과정은 읽는 속도를 늦추더라도 이해의 정확성을 높일 수 있습니다.|This checking may improve accuracy even if it slows reading.
 이 독서 기록에는 모르는 단어의 수만으로 이해도를 평가하기 어렵다는 한계가 드러납니다.|This reading record shows that counting unfamiliar words alone cannot adequately assess comprehension.
 모든 단어를 알아도 글의 의도나 생략된 관계를 놓칠 수 있기 때문입니다.|Even someone who knows every word may miss the writer's purpose or an unstated relationship.
 다음 독서에서는 단어 뜻과 함께 글의 핵심 내용을 한 문장으로 정리하기로 했습니다.|For the next reading, I decided to summarize the main point as well as check word meanings.`,
 `지금 비가 와요.|It is raining now.
 저는 친구를 만나요.|I meet a friend.
 우산이 하나 있어요.|We have one umbrella.
 우산이 작아서 우리는 걸음을 맞추어 걸었습니다.|The umbrella was small, so we matched our pace.
 친구가 더 젖지 않도록 우산을 가운데로 옮겼습니다.|I moved the umbrella to the middle so my friend would not get wetter.
 집에 도착한 뒤 젖은 우산을 펴서 말렸습니다.|After arriving home, I opened the wet umbrella to dry it.
 다음에는 외출 전에 날씨를 확인하겠다고 생각했습니다.|I thought I would check the weather before going out next time.
 우산을 나누어 쓰는 일에는 물건을 빌려주는 것 이상의 조정이 필요했습니다.|Sharing an umbrella required more coordination than merely lending an object.
 서로의 속도와 우산의 위치를 계속 맞추어야 했기 때문입니다.|We had to keep adjusting our speed and the umbrella's position.
 도움을 주려는 의도가 있어도 상대가 실제로 불편한지는 물어보아야 합니다.|Even with helpful intentions, we should ask whether the other person is uncomfortable.
 저는 친구에게 우산이 충분히 가리는지 묻고 위치를 다시 바꾸었습니다.|I asked my friend whether the umbrella provided enough cover and adjusted it again.
 이 사례에서 협력의 성과는 우산의 소유자가 누구인지로 판단할 수 없습니다.|In this case, successful cooperation cannot be judged by who owns the umbrella.
 두 사람이 비를 얼마나 피했는지와 서로의 요구를 반영했는지가 더 적절한 기준입니다.|More suitable criteria are how well both avoided the rain and whether their needs were considered.
 같은 도움이라도 상황과 상대에 따라 필요한 방식이 달라질 수 있습니다.|The appropriate form of help can vary with the situation and the person.`,
 `여기는 공원이에요.|This is a park.
 나무가 많아요.|There are many trees.
 저는 벤치에 앉아요.|I sit on a bench.
 가까운 나무에서 새가 울었지만 처음에는 보이지 않았습니다.|A bird sang in a nearby tree, but I could not see it at first.
 소리가 나는 쪽을 천천히 살피자 나뭇가지 위의 새를 찾았습니다.|Looking slowly toward the sound, I found the bird on a branch.
 새가 날아간 뒤에는 벤치 주변의 쓰레기를 주웠습니다.|After the bird flew away, I picked up litter around the bench.
 공원을 떠나기 전에 쓰레기를 수거함에 넣었습니다.|Before leaving, I put the litter in a bin.
 공원은 휴식 공간인 동시에 여러 생물이 살아가는 장소입니다.|A park is both a place for rest and a habitat for living things.
 사람이 편하다는 이유만으로 모든 공간을 같은 방식으로 관리할 수는 없습니다.|Human convenience alone does not justify managing every area in the same way.
 새가 쉬는 나무 주변에서는 큰 소리를 줄이는 배려가 필요할 수 있습니다.|Keeping noise down near trees where birds rest may be appropriate.
 이용자의 활동과 생물의 서식 환경을 함께 고려해야 하기 때문입니다.|Both visitors' activities and wildlife habitats need consideration.
 한 번 새를 보았다는 사실만으로 공원의 생태적 상태를 평가할 수는 없습니다.|Seeing a bird once is insufficient to evaluate a park's ecological condition.
 계절과 시간에 따라 관찰 결과가 달라질 수 있으므로 반복 기록이 필요합니다.|Repeated records are needed because observations may vary by season and time.
 개인의 짧은 경험과 지속적인 조사 자료는 서로 다른 근거로 다루어야 합니다.|A brief personal experience and sustained survey data must be treated as different forms of evidence.`,
 `여기는 시장이에요.|This is a market.
 채소가 있어요.|There are vegetables.
 저는 과일을 봐요.|I look at fruit.
 같은 사과도 가게마다 가격이 달라 두 곳을 비교했습니다.|Prices for the same apples differed between shops, so I compared two shops.
 한 가게는 가격이 낮았지만 사과의 크기도 조금 작았습니다.|One shop had a lower price, but its apples were also a little smaller.
 저는 필요한 양을 생각해서 작은 사과 세 개를 골랐습니다.|Considering how much I needed, I chose three small apples.
 상인은 사과를 봉지에 담으며 보관 방법을 알려 주었습니다.|The vendor put them in a bag and explained how to store them.
 싼 상품을 고르는 일과 필요한 상품을 고르는 일은 항상 일치하지 않습니다.|Choosing the cheapest item and choosing what is needed do not always coincide.
 가격만 비교하면 크기나 품질처럼 다른 조건을 놓칠 수 있습니다.|Comparing prices alone can overlook size or quality.
 반대로 큰 상품을 사도 다 먹지 못하면 낭비가 생깁니다.|Conversely, buying a larger item may create waste if it cannot all be eaten.
 따라서 구매 기준은 가격과 실제 소비량을 함께 반영해야 합니다.|Purchase criteria should therefore consider both price and actual consumption.
 이 경험은 어느 가게가 언제나 더 경제적인지를 증명하지 않습니다.|This experience does not prove that one shop is always more economical.
 상품의 상태와 구매 시점에 따라 비교 결과가 달라질 수 있기 때문입니다.|The result can change with the products' condition and the time of purchase.
 일반적인 결론을 내리기 전에 비교 조건을 명확하게 제시할 필요가 있습니다.|The comparison conditions need to be stated clearly before drawing a general conclusion.`,
 `저는 요리해요.|I cook.
 채소를 씻어요.|I wash vegetables.
 냄비가 있어요.|There is a pot.
 조리법을 보면서 재료를 순서대로 넣었습니다.|I followed the recipe and added the ingredients in order.
 불이 너무 세서 물이 빨리 줄어들었습니다.|The heat was too high, so the water decreased quickly.
 물을 조금 더 넣고 불을 낮추자 국이 천천히 끓었습니다.|I added a little water and lowered the heat, and the soup simmered slowly.
 저는 다음 요리를 위해 바꾼 방법을 기록했습니다.|I recorded the changes for the next time I cooked.
 조리법은 출발점이지만 실제 조리 조건까지 모두 같게 만들지는 못합니다.|A recipe is a starting point but does not make all cooking conditions identical.
 냄비의 크기나 불의 세기에 따라 같은 시간에도 결과가 달라집니다.|Pot size or heat level can change the result even with the same cooking time.
 결과가 예상과 다를 때는 어떤 조건이 달랐는지 살펴보는 것이 유용합니다.|When a result differs from expectations, it helps to examine which conditions differed.
 저는 소금보다 먼저 물의 양과 불의 세기를 확인했습니다.|I checked the water quantity and heat before considering the salt.
 이번 성공만으로 조리법을 완전히 익혔다고 판단하기는 이릅니다.|One success is too little to conclude that I have mastered the recipe.
 여러 조건을 동시에 바꾸면 어떤 변화가 효과를 냈는지 구분하기도 어렵습니다.|Changing several conditions at once also makes it hard to identify which change helped.
 다음에는 바꾸는 조건을 줄여 결과를 비교하기로 했습니다.|Next time, I decided to change fewer conditions and compare the results.`,
 `저는 버스를 기다려요.|I wait for a bus.
 사람이 많아요.|There are many people.
 줄을 서요.|I stand in line.
 안내 화면에는 버스가 오 분 뒤에 온다고 나왔습니다.|The display said the bus would arrive in five minutes.
 하지만 도로가 막혀 실제로는 십 분 뒤에 도착했습니다.|Traffic was heavy, so it actually arrived ten minutes later.
 저는 기다리는 동안 다음 약속에 늦는다고 연락했습니다.|While waiting, I informed someone that I would be late for our appointment.
 버스에 탄 뒤 빈자리가 없어 손잡이를 잡았습니다.|After boarding, I held a handrail because there were no empty seats.
 도착 안내는 계획에 도움이 되지만 확정된 약속과 같지는 않습니다.|Arrival information helps with planning but is not a guaranteed appointment.
 교통 상황처럼 예측하기 어려운 조건이 이동 시간에 영향을 주기 때문입니다.|Conditions that are hard to predict, such as traffic, affect journey time.
 안내가 틀렸다고 느낄 때는 표시가 예측값인지 확정값인지 구분해야 합니다.|When a display seems wrong, we must distinguish predictions from confirmed values.
 저는 중요한 약속에는 기다릴 시간을 더 넉넉히 잡기로 했습니다.|I decided to allow extra waiting time for important appointments.
 한 번의 지연만으로 안내 시스템 전체가 무용하다고 결론 내릴 수는 없습니다.|A single delay does not establish that the entire information system is useless.
 정확도를 평가하려면 여러 시간대의 예측과 실제 도착 기록을 비교해야 합니다.|Accuracy should be evaluated by comparing predictions and actual arrivals across different times.
 이용자가 필요한 것은 오차가 없다는 약속보다 예측의 한계를 이해할 수 있는 정보일 수 있습니다.|Users may need information about a prediction's limits more than a promise of zero error.`,
 `교실에 친구가 와요.|A friend comes into the classroom.
 저는 인사해요.|I say hello.
 이름을 물어요.|I ask their name.
 새 친구는 노래 듣기를 좋아한다고 말했습니다.|The new friend said they enjoyed listening to songs.
 우리는 같은 가수를 좋아해서 금방 이야기를 시작했습니다.|We liked the same singer, so it was easy to start talking.
 좋아하는 노래는 달랐지만 서로 한 곡씩 추천했습니다.|Our favorite songs differed, but we each recommended one.
 다음 날에는 추천받은 노래를 듣고 다시 이야기했습니다.|The next day, we listened to the recommendations and talked again.
 공통점은 대화를 시작하게 했지만 차이는 대화를 이어 가는 소재가 되었습니다.|A shared interest started the conversation, while differences helped sustain it.
 같은 취향이 있어야만 친구가 될 수 있다는 생각은 이 경험과 맞지 않았습니다.|The idea that friendship requires identical tastes did not fit this experience.
 중요한 것은 다른 취향을 틀린 답처럼 취급하지 않는 태도였습니다.|What mattered was not treating a different preference as a wrong answer.
 상대의 추천 이유를 묻자 음악을 듣는 새로운 방법을 알게 되었습니다.|Asking why my friend recommended a song revealed a new way to listen.
 다만 한 사람의 반응을 모든 새 친구에게 적용할 수는 없습니다.|However, one person's response cannot be generalized to all new friends.
 취향을 공개하고 싶은 정도와 대화 속도는 사람마다 다를 수 있습니다.|People may differ in how much they want to share and how fast they want a conversation to develop.
 친해지려는 의도와 함께 상대의 선택권도 존중할 필요가 있습니다.|Along with wanting friendship, we need to respect the other person's choices.`,
 `오늘은 추워요.|It is cold today.
 장갑이 없어요.|My glove is missing.
 저는 길을 봐요.|I look along the road.
 주머니를 다시 확인했지만 다른 한 짝만 있었습니다.|I checked my pockets again, but only the other glove was there.
 마지막으로 장갑을 벗은 곳을 생각하며 학교 쪽으로 걸었습니다.|I walked toward school, recalling where I had last taken it off.
 문 앞에서 장갑을 찾고 두 짝을 가방에 함께 넣었습니다.|I found it by the gate and put both gloves together in my bag.
 집에 돌아온 뒤에는 장갑을 둘 장소를 정했습니다.|After returning home, I chose a fixed place for my gloves.
 물건을 찾는 과정에서는 기억을 그대로 믿기보다 실제 흔적과 비교하는 것이 도움이 됩니다.|When searching for an object, comparing memory with actual clues can help.
 저는 장갑을 잃어버린 시점과 없다는 사실을 알아차린 시점을 처음에는 혼동했습니다.|At first I confused when I lost the glove with when I noticed it was missing.
 두 시점을 구분하자 살펴볼 길의 범위를 좁힐 수 있었습니다.|Distinguishing the two let me narrow down the route to search.
 해결에 도움이 된 것은 막연히 더 빨리 걷는 일이 아니라 정보를 정리하는 일이었습니다.|Organizing information helped more than simply walking faster.
 이 방법으로 장갑을 찾았다고 해서 기억이 항상 정확하다고 볼 수는 없습니다.|Finding the glove this way does not mean memory is always accurate.
 누군가 물건을 옮겼다면 지나온 길을 되짚는 것만으로는 부족했을 것입니다.|If someone had moved it, retracing the route alone would not have sufficed.
 같은 문제라도 가능한 원인이 달라지면 찾는 방법도 조정해야 합니다.|Search methods must change when the possible causes of a problem differ.`,
 `주말에 여행해요.|We travel on the weekend.
 가족과 지도를 봐요.|I look at a map with my family.
 기차를 타요.|We take a train.
 가고 싶은 곳이 많아서 먼저 이동 시간을 계산했습니다.|We wanted to visit many places, so we calculated travel time first.
 역에서 먼 장소는 이번 일정에서 빼기로 했습니다.|We decided to leave out places far from the station this time.
 점심을 먹고 쉴 시간도 계획에 넣었습니다.|We included time for lunch and rest.
 덕분에 마지막 기차를 타기 위해 서두르지 않아도 되었습니다.|As a result, we did not need to rush for the last train.
 여행 계획의 충실함을 방문 장소의 수만으로 평가하기는 어렵습니다.|A good travel plan cannot be judged only by the number of places visited.
 이동과 휴식에 필요한 시간을 빼면 실제로 즐길 시간이 줄어들기 때문입니다.|Ignoring travel and rest time reduces the time available for enjoyment.
 이번 계획에서는 많은 장소보다 가족이 함께 편하게 움직이는 것을 우선했습니다.|This plan prioritized comfortable travel together over visiting many places.
 따라서 제외한 장소가 있다는 사실은 계획의 실패를 뜻하지 않습니다.|Leaving places out therefore does not mean the plan failed.
 그렇다고 모든 여행에 같은 우선순위를 적용해야 하는 것은 아닙니다.|That does not mean every trip should follow the same priorities.
 여행 목적과 참여자의 필요가 다르면 적절한 일정도 달라집니다.|Different purposes and participants' needs call for different schedules.
 계획을 평가할 때는 처음 정한 목표와 실제 경험을 함께 검토해야 합니다.|A plan should be evaluated against both its original goal and the actual experience.`,
 `제 전화기는 방에 있어요.|My phone is in my room.
 저는 친구와 있어요.|I am with a friend.
 친구의 말을 들어요.|I listen to my friend.
 처음에는 새 메시지가 왔는지 자꾸 확인하고 싶었습니다.|At first, I kept wanting to check for new messages.
 잠시 뒤에는 친구의 표정과 말에 더 주의를 기울였습니다.|After a while, I paid more attention to my friend's expression and words.
 헤어진 뒤 집에서 필요한 연락을 확인했습니다.|After we parted, I checked necessary messages at home.
 다음에는 전화기를 쓰지 않는 시간을 미리 알리기로 했습니다.|Next time, I decided to tell others in advance when I would be unavailable by phone.
 전화기를 멀리 둔 것은 연락 자체를 거부하기 위해서가 아니었습니다.|Putting the phone away was not intended to reject communication itself.
 눈앞의 대화와 다른 연락을 처리하는 시간을 구분하려는 선택이었습니다.|It was a choice to separate face-to-face conversation from handling other messages.
 그러나 긴급한 연락이 필요한 사람에게는 같은 방법이 불편을 줄 수 있습니다.|The same approach could inconvenience someone who needs urgent contact.
 사용 시간을 줄이는 목표와 필요한 연결을 유지하는 목표를 함께 고려해야 합니다.|Reducing phone use and maintaining necessary contact must both be considered.
 하루의 경험만으로 전화기 사용이 모든 대화를 방해한다고 단정할 수는 없습니다.|One day's experience does not establish that phone use disrupts every conversation.
 사용 목적과 방식에 따라 대화를 돕는 도구가 될 수도 있기 때문입니다.|Depending on its purpose and use, a phone can also support conversation.
 중요한 판단 기준은 기기의 유무보다 실제 상호작용에 미친 영향입니다.|The important criterion is its effect on interaction rather than its mere presence.`,
 `작은 나무가 있어요.|There is a small tree.
 학생들이 물을 줘요.|Students water it.
 이름표를 붙여요.|They attach a name tag.
 학생들은 번갈아 나무를 돌보기로 했습니다.|The students decided to take turns caring for the tree.
 비가 온 다음 날에는 흙이 젖어 있어서 물을 더 주지 않았습니다.|The day after rain, the soil was wet, so they did not add more water.
 잎이 조금 처진 날에는 선생님과 상태를 살펴보았습니다.|When the leaves drooped a little, they examined the tree with their teacher.
 나무의 키와 잎의 모습을 매주 공책에 기록했습니다.|They recorded its height and leaves each week.
 나무를 돌보는 일은 정해진 행동을 매일 반복하는 것만으로 끝나지 않았습니다.|Caring for the tree involved more than repeating a fixed action daily.
 날씨와 흙의 상태에 따라 필요한 관리가 달라졌기 때문입니다.|Its needs changed with the weather and soil conditions.
 책임을 나누어 맡더라도 관찰 내용을 공유하지 않으면 관리가 어긋날 수 있습니다.|Even with shared responsibilities, care can become inconsistent if observations are not shared.
 학생들은 물을 준 날짜뿐 아니라 흙의 상태도 함께 적었습니다.|The students recorded soil conditions as well as watering dates.
 키가 자랐다는 결과만으로 어떤 관리 방법이 가장 좋았는지 판단하기는 어렵습니다.|Growth in height alone does not establish which care method was best.
 계절과 나무의 종류 같은 조건이 성장에 영향을 주기 때문입니다.|Season and tree species also affect growth.
 관찰 기록은 성급한 성공 선언보다 다음 관리 결정을 돕는 근거로 쓰여야 합니다.|Observation records should support future care decisions rather than premature claims of success.`,
 `친구와 약속이 있어요.|I have an appointment with a friend.
 저는 시계를 봐요.|I look at the clock.
 친구에게 전화해요.|I call my friend.
 친구는 이미 약속 장소에서 기다리고 있었습니다.|My friend was already waiting at the meeting place.
 저는 변명보다 먼저 늦어서 미안하다고 말했습니다.|Before giving an excuse, I apologized for being late.
 도착할 수 있는 시간을 확인하고 친구에게 알려 주었습니다.|I checked when I could arrive and told my friend.
 다음 약속은 달력과 알림에 함께 기록했습니다.|I recorded the next appointment in both a calendar and a reminder.
 약속을 지키지 못했을 때 사과만으로 상대의 기다린 시간이 사라지지는 않습니다.|An apology cannot erase the time someone spent waiting after a broken appointment.
 상대가 다음 행동을 정할 수 있도록 정확한 정보를 주는 일도 필요합니다.|Accurate information is also needed so the other person can decide what to do next.
 저는 곧 간다는 말 대신 예상 도착 시간을 구체적으로 전했습니다.|Instead of saying I would come soon, I gave a specific expected arrival time.
 이후에는 실제로 같은 실수를 줄이는 행동이 신뢰 회복에 중요했습니다.|Later, actions that reduced repeated mistakes mattered for restoring trust.
 그렇다고 한 번의 실수로 그 사람의 성격 전체를 평가할 수는 없습니다.|A single mistake does not justify judging a person's entire character.
 반복 여부와 이후의 대응을 함께 보아야 더 타당한 판단을 할 수 있습니다.|A sounder judgment considers repetition and the person's subsequent response.
 신뢰는 사과의 문구만이 아니라 시간이 지나며 확인되는 행동과 관련됩니다.|Trust relates to behavior observed over time as well as the wording of an apology.`,
 `여기는 처음 와요.|This is my first time here.
 길이 많아요.|There are many streets.
 저는 지도를 받아요.|I receive a map.
 안내소 직원은 현재 위치를 지도에 표시해 주었습니다.|The information-desk worker marked my current location on the map.
 저는 찾는 건물의 이름을 다시 확인했습니다.|I checked the name of the building I was seeking again.
 비슷한 이름의 건물이 두 개 있어서 주소도 살펴보았습니다.|There were two buildings with similar names, so I checked the address too.
 길모퉁이의 표지판을 확인한 뒤 목적지에 도착했습니다.|After checking a sign at the corner, I reached my destination.
 낯선 장소에서는 이름을 안다는 것과 정확한 위치를 안다는 것이 다를 수 있습니다.|In an unfamiliar place, knowing a name and knowing an exact location can differ.
 이름만으로 길을 찾으면 비슷한 시설을 혼동할 가능성이 있습니다.|Searching by name alone can lead to confusion between similar facilities.
 지도와 표지판의 정보를 대조한 것은 이런 혼동을 줄이기 위한 행동이었습니다.|Comparing the map and signs was a way to reduce that confusion.
 두 자료가 다를 때는 어느 쪽이 최신 정보인지도 확인해야 합니다.|When two sources differ, we must also check which is more current.
 목적지에 도착했다는 사실만으로 모든 안내 정보가 정확했다고 볼 수는 없습니다.|Reaching the destination does not mean every piece of guidance was accurate.
 중간에 잘못된 정보를 다른 단서로 바로잡았을 수도 있기 때문입니다.|Another clue may have corrected inaccurate information along the way.
 정보의 신뢰도를 평가할 때는 결과뿐 아니라 확인 과정도 살펴야 합니다.|Evaluating information reliability requires considering the checking process as well as the result.`,
 `우리 반은 공연을 해요.|Our class puts on a performance.
 저는 친구와 연습해요.|I practice with a friend.
 노래를 불러요.|We sing a song.
 어떤 노래를 부를지 정할 때 의견이 나뉘었습니다.|Opinions differed about which song to sing.
 먼저 모두가 부를 수 있는 노래라는 기준을 정했습니다.|We first agreed on a criterion: everyone should be able to sing the song.
 기준에 맞는 두 곡을 짧게 불러 보고 한 곡을 골랐습니다.|We briefly tried two suitable songs and chose one.
 노래를 부르지 않는 친구들은 무대와 안내를 맡았습니다.|Classmates who did not sing handled the stage and guidance.
 공동 작업에서는 모든 사람이 같은 역할을 맡아야 공정한 것은 아닙니다.|Fairness in shared work does not require everyone to have the same role.
 필요한 역할과 각자의 가능성을 함께 고려하면 참여 방식이 다양해질 수 있습니다.|Considering needed roles and individual capabilities can allow varied forms of participation.
 다만 역할이 다르다는 이유로 어떤 기여를 보이지 않는 일처럼 취급해서는 안 됩니다.|However, different roles must not make some contributions invisible.
 공연을 마친 뒤에는 무대 밖에서 도운 친구들의 이름도 함께 소개했습니다.|After the performance, we also named the classmates who helped offstage.
 관객의 박수만으로 준비 과정의 공정성을 평가할 수는 없습니다.|Audience applause alone cannot establish fairness in the preparation process.
 역할을 선택할 기회와 부담의 분배도 확인해야 하기 때문입니다.|Opportunities to choose roles and the distribution of work must also be examined.
 좋은 결과와 공정한 과정은 서로 관련되지만 동일한 평가 항목은 아닙니다.|A good outcome and a fair process are related but distinct criteria.`,
 `오늘은 비가 와요.|It is raining today.
 소풍을 못 가요.|We cannot go on the picnic.
 교실에서 놀아요.|We play in the classroom.
 처음에는 모두 아쉬워했지만 할 수 있는 일을 적어 보았습니다.|Everyone was disappointed at first, but we listed things we could do.
 교실에서 할 수 있는 그림 놀이와 보드게임을 골랐습니다.|We chose drawing activities and board games suitable for the classroom.
 조용히 쉬고 싶은 친구를 위해 읽을 책도 준비했습니다.|We also prepared books for classmates who wanted quiet rest.
 하루가 끝날 때 각자 즐거웠던 활동을 이야기했습니다.|At the end of the day, we each discussed an activity we enjoyed.
 계획을 바꾸었다는 사실이 원래 목표를 포기했다는 뜻은 아니었습니다.|Changing the plan did not mean abandoning the original goal.
 함께 즐겁게 시간을 보낸다는 목표는 실내 활동으로도 추구할 수 있었기 때문입니다.|The goal of enjoying time together could also be pursued indoors.
 다만 모든 학생이 같은 활동을 좋아한다고 가정하지는 않았습니다.|We did not assume, however, that every student liked the same activity.
 선택지를 남겨 두는 것이 바뀐 계획에 참여하기 쉽게 만들었습니다.|Keeping options open made it easier to participate in the revised plan.
 즐거웠다는 몇 사람의 평가만으로 모든 학생이 만족했다고 결론 내릴 수는 없습니다.|A few positive comments do not show that every student was satisfied.
 말하지 않은 학생의 경험도 들을 기회가 필요합니다.|There must also be a chance to hear from students who did not speak.
 계획의 성공을 판단하려면 목표와 참여자의 다양한 반응을 함께 살펴야 합니다.|Judging the plan's success requires considering its goal and participants' varied responses.`,
 `길에 사람이 있어요.|There is a person on the street.
 그 사람은 길을 몰라요.|That person does not know the way.
 저는 표지판을 봐요.|I look at a sign.
 저는 도움이 필요한지 먼저 물었습니다.|I first asked whether help was needed.
 그 사람은 역을 찾는다며 지도 화면을 보여 주었습니다.|The person showed me a map and said they were looking for the station.
 우리는 길을 막지 않는 곳으로 옮겨 방향을 확인했습니다.|We moved somewhere out of the way to check the direction.
 저는 아는 길만 안내하고 모르는 출구 번호는 함께 찾아보았습니다.|I explained only the route I knew and looked up the unfamiliar exit number together.
 도움을 줄 때는 자신이 아는 범위와 모르는 범위를 구분하는 것이 중요합니다.|When helping, it is important to distinguish what we know from what we do not.
 자신 있게 말하는 것만으로 안내의 정확성이 보장되지는 않기 때문입니다.|Speaking confidently does not guarantee accurate guidance.
 상대가 실제로 원하는 도움을 확인하는 과정도 필요합니다.|We also need to check what help the person actually wants.
 저는 대신 목적지를 정하지 않고 그 사람이 찾는 역을 확인했습니다.|Rather than choose a destination for them, I confirmed the station they wanted.
 이 상황에서 친절의 정도를 안내한 말의 길이로만 평가할 수는 없습니다.|Helpfulness here cannot be measured only by how long the explanation was.
 필요한 정보의 정확성과 상대의 선택권을 존중했는지가 더 적절한 기준입니다.|Better criteria are information accuracy and respect for the person's choices.
 도움의 결과를 확인하지 않았다면 실제로 도움이 되었다고 단정하지 않는 태도도 필요합니다.|Without checking the outcome, we should also avoid assuming that the help was effective.`,
 `오래된 사진이 있어요.|There is an old photograph.
 사진에 가족이 있어요.|My family is in the photograph.
 저는 가족에게 물어요.|I ask my family about it.
 할머니는 사진을 찍은 날에 시장에 갔다고 기억했습니다.|Grandmother remembered going to the market on the day of the photograph.
 아버지는 그날이 아니라 다음 날이었다고 말했습니다.|Father said it was the following day, not that day.
 사진 뒤의 날짜를 확인하자 사진을 찍은 날은 알 수 있었습니다.|The date on the back established when the photograph was taken.
 그러나 시장에 간 날짜는 여전히 확실하지 않았습니다.|The date of the market visit remained uncertain, however.
 같은 경험을 한 사람들도 세부 내용을 다르게 기억할 수 있습니다.|People who shared an experience may remember details differently.
 기억의 차이가 있다고 해서 누군가 일부러 거짓말한다고 볼 수는 없습니다.|A difference in memory does not necessarily mean someone is deliberately lying.
 사진은 일부 정보를 확인하게 했지만 모든 질문에 답하지는 못했습니다.|The photograph confirmed some information but could not answer every question.
 저는 확인된 날짜와 아직 불확실한 기억을 나누어 적었습니다.|I recorded the confirmed date separately from the uncertain memories.
 기록이 있다는 이유만으로 그 기록이 모든 맥락을 담고 있다고 가정해서는 안 됩니다.|The existence of a record does not mean it contains every aspect of the context.
 사진에 나타나지 않은 행동이나 사건은 다른 자료가 있어야 검토할 수 있습니다.|Actions or events outside the photograph require other evidence to examine.
 과거를 해석할 때는 자료가 보여 주는 것과 해석자가 덧붙인 것을 구분해야 합니다.|When interpreting the past, we must distinguish what a source shows from what an interpreter adds.`,
 `화분이 두 개 있어요.|There are two plant pots.
 저는 물을 줘요.|I water them.
 햇빛이 있어요.|There is sunlight.
 다른 화분은 창문에서 조금 떨어진 곳에 두었습니다.|I placed the other pot a little away from the window.
 두 화분의 잎과 키를 같은 시간에 기록했습니다.|I recorded both plants' leaves and height at the same time of day.
 며칠 뒤 한 화분의 잎이 더 짙어 보였습니다.|After several days, one plant's leaves appeared darker.
 저는 빛의 차이가 원인인지 알아보기 위해 기록을 더 모으기로 했습니다.|I decided to collect more records to examine whether the difference in light was the cause.
 물의 양을 같게 했다고 해서 모든 다른 조건까지 같아진 것은 아닙니다.|Giving equal amounts of water did not make every other condition identical.
 처음 식물의 크기나 흙의 상태가 달랐을 가능성도 있습니다.|The plants' initial size or soil conditions may also have differed.
 따라서 관찰된 차이를 햇빛 하나의 효과로 바로 설명해서는 안 됩니다.|The observed difference therefore should not immediately be attributed to sunlight alone.
 비교 실험에서는 바꾸려는 조건과 일정하게 유지할 조건을 미리 구분해야 합니다.|A comparative experiment should distinguish in advance the factor to change from those to keep constant.
 두 화분만 관찰한 결과를 모든 식물에 일반화하기는 어렵습니다.|Results from just two pots are difficult to generalize to all plants.
 측정 방식과 관찰 기간을 명확히 기록해야 다른 사람이 같은 조건을 재현할 수 있습니다.|Clear records of measurement methods and observation periods help others reproduce the conditions.
 결론을 유보한다는 것은 관찰을 버리는 것이 아니라 근거에 맞는 범위로 주장을 제한하는 것입니다.|Withholding a conclusion means limiting a claim to its evidence, not discarding the observation.`,
 `친구가 생각해요.|My friend is thinking.
 두 방법이 있어요.|There are two options.
 저는 친구의 말을 들어요.|I listen to my friend.
 친구는 새 수업을 들을지 혼자 공부할지 고민했습니다.|My friend was deciding between taking a new course and studying alone.
 우리는 비용과 공부 시간을 종이에 나누어 적었습니다.|We listed costs and study time in separate columns.
 저는 제가 좋아하는 방법과 친구에게 맞는 방법이 다를 수 있다고 말했습니다.|I said that my preferred method might differ from the one suitable for my friend.
 친구는 먼저 일주일 동안 혼자 공부해 본 뒤 다시 결정하기로 했습니다.|My friend decided to try independent study for a week before deciding again.
 선택을 돕는 일은 반드시 상대를 대신해 정답을 고르는 일은 아닙니다.|Helping with a choice does not necessarily mean choosing the answer for someone else.
 비교 기준을 정리하고 부족한 정보를 찾는 방식으로도 도움을 줄 수 있습니다.|We can help by organizing criteria and identifying missing information.
 이 사례에서는 비용보다 지속할 수 있는 시간이 더 중요한 기준이 되었습니다.|In this case, available sustainable study time mattered more than cost.
 같은 선택지도 사람의 목표와 조건에 따라 다른 평가를 받을 수 있습니다.|The same option may be evaluated differently depending on a person's goals and circumstances.
 일주일의 시도는 참고 자료가 될 수 있지만 장기적인 성과까지 보장하지는 않습니다.|A week's trial can provide information but cannot guarantee long-term results.
 결과를 평가하려면 무엇을 배웠는지뿐 아니라 실제로 공부를 지속했는지도 확인해야 합니다.|Evaluation should examine both learning and whether study was actually sustained.
 최종 선택의 권한과 결과를 함께 검토할 기회는 친구에게 남겨 두었습니다.|The final choice and the chance to review its outcome remained with my friend.`
 ];
 const branches = [
 ['다음 날에는 알람을 조금 늦게 맞추고 같은 정리를 해 보았습니다.','The next day I set the alarm a little later and tried the same tidying routine.'],
 ['다음 주에는 사전 없이 먼저 읽고 이해한 내용을 친구에게 설명했습니다.','The next week I read without a dictionary first and explained my understanding to a friend.'],
 ['다음 비 오는 날에는 제가 큰 우산을 가져와 친구와 나누어 썼습니다.','On the next rainy day I brought a large umbrella and shared it with my friend.'],
 ['다음 방문에는 같은 벤치에서 다른 시간의 새소리를 기록했습니다.','On my next visit I recorded birdsong at a different time from the same bench.'],
 ['다음 장보기에서는 가격표와 함께 남은 과일의 양을 먼저 확인했습니다.','Before my next shopping trip I checked the remaining fruit as well as the prices.'],
 ['두 번째 요리에서는 물의 양만 바꾸고 나머지 조건을 같게 두었습니다.','For the second attempt I changed only the water quantity and kept the other conditions the same.'],
 ['다음 약속에는 출발 시간을 앞당겨 버스가 늦어도 기다릴 여유가 있었습니다.','For the next appointment I left earlier, leaving spare time even if the bus was delayed.'],
 ['다음 대화에서는 제가 모르는 가수를 친구에게 소개해 달라고 했습니다.','In our next conversation I asked my friend to introduce an unfamiliar singer.'],
 ['다음 외출부터는 장갑을 벗으면 가방의 같은 주머니에 넣었습니다.','On subsequent outings I put my gloves in the same bag pocket whenever I took them off.'],
 ['다음 여행에는 가족이 각자 가장 가고 싶은 장소를 하나씩 골랐습니다.','For the next trip each family member chose one place they most wanted to visit.'],
 ['두 번째 시도에서는 필요한 연락 시간을 정한 뒤 전화기를 멀리 두었습니다.','For my second attempt I arranged times for necessary messages before putting the phone away.'],
 ['다음 주에는 담당 학생이 바뀌어도 나무의 상태를 알 수 있도록 기록을 공유했습니다.','The next week we shared records so a new student in charge could understand the tree\'s condition.'],
 ['다음 약속에서는 제가 먼저 도착해 친구를 기다렸습니다.','At the next appointment I arrived first and waited for my friend.'],
 ['다음 방문에서는 출발 전에 건물의 이름과 주소를 함께 저장했습니다.','For my next visit I saved both the building name and address before leaving.'],
 ['두 번째 공연에서는 무대 밖의 역할도 학생들이 먼저 선택하게 했습니다.','For the second performance students could also choose offstage roles first.'],
 ['다음 소풍 계획에서는 비가 올 때 할 활동도 미리 함께 골랐습니다.','When planning the next picnic we also chose rainy-day activities in advance.'],
 ['다음에 길을 묻는 사람에게는 먼저 어느 출구로 가고 싶은지 확인했습니다.','The next time someone asked directions, I first checked which exit they wanted.'],
 ['다음 가족 모임에서는 날짜가 적힌 다른 사진도 가져와 기억과 비교했습니다.','At the next family gathering we brought other dated photographs to compare with our memories.'],
 ['다음 관찰에서는 처음 크기가 비슷한 식물을 고르고 흙의 양도 같게 했습니다.','For the next observation I chose plants of similar initial size and equalized the soil quantity.'],
 ['일주일 뒤 친구는 공부 기록을 확인한 뒤 수업을 병행하기로 결정했습니다.','A week later my friend reviewed the study record and decided to add a course.']
 ];
 const alternatives = [
 '저는 방에 있어요.|I am in my room.\n아침 햇빛이 밝아요.|The morning sunlight is bright.\n오늘은 공부해요.|I study today.',
 '저는 책을 읽어요.|I read a book.\n새 단어가 있어요.|There is a new word.\n공책에 써요.|I write it in my notebook.',
 '저는 집에 가요.|I go home.\n친구도 같이 가요.|My friend goes with me too.\n우산을 같이 써요.|We share an umbrella.',
 '공원에 아이들이 있어요.|There are children in the park.\n공을 가지고 놀아요.|They play with a ball.\n저는 새소리를 들어요.|I listen to birdsong.',
 '할머니와 시장에 가요.|I go to the market with Grandmother.\n저는 가격을 봐요.|I look at the prices.\n할머니는 채소를 골라요.|Grandmother chooses vegetables.',
 '오늘 점심을 만들어요.|I make lunch today.\n저는 혼자 있어요.|I am alone.\n재료를 냄비에 넣어요.|I put ingredients in a pot.',
 '정류장에 사람이 있어요.|There are people at the bus stop.\n버스가 늦게 와요.|The bus comes late.\n우리는 차례로 타요.|We board in order.',
 '새 학생이 와요.|A new student arrives.\n저는 먼저 말해요.|I speak first.\n음악 이야기를 해요.|We talk about music.',
 '장갑 한 짝을 찾아요.|I look for one glove.\n학교 문에 가요.|I go to the school gate.\n거기에 장갑이 있어요.|The glove is there.',
 '가족과 주말에 떠나요.|I leave with my family on the weekend.\n지도에 역이 있어요.|There is a station on the map.\n기차표를 사요.|We buy train tickets.',
 '오늘은 전화기를 안 봐요.|I do not look at my phone today.\n친구가 이야기해요.|My friend talks.\n저는 대화에 집중해요.|I focus on the conversation.',
 '학교에 나무를 심어요.|We plant a tree at school.\n나무는 아직 작아요.|The tree is still small.\n우리는 나무를 돌봐요.|We care for the tree.',
 '친구가 저를 기다려요.|My friend waits for me.\n저는 미안하다고 해요.|I say I am sorry.\n달력에 약속을 써요.|I write the appointment on my calendar.',
 '저는 새 도시에 와요.|I come to a new city.\n안내소에서 물어요.|I ask at the information desk.\n지도를 보고 걸어요.|I walk using the map.',
 '친구들과 공연을 준비해요.|I prepare a performance with my friends.\n서로 생각이 달라요.|Our ideas differ.\n우리는 역할을 나눠요.|We share the roles.',
 '소풍 날 비가 와요.|It rains on the picnic day.\n우리는 안에서 놀아요.|We play indoors.\n다른 활동을 찾아요.|We find another activity.',
 '어떤 사람이 역을 찾아요.|Someone is looking for a station.\n저는 길을 알려 줘요.|I give directions.\n같이 지도를 봐요.|We look at a map together.',
 '서랍에 사진이 있어요.|There is a photograph in a drawer.\n옛날 건물이 보여요.|An old building is visible.\n가족이 그날을 이야기해요.|My family talks about that day.',
 '저는 식물을 봐요.|I look at the plants.\n두 화분에 물을 줘요.|I water two plant pots.\n하나는 햇빛 아래에 둬요.|I place one in sunlight.',
 '친구는 선택을 고민해요.|My friend considers a choice.\n저는 답을 정하지 않아요.|I do not decide the answer.\n같이 좋은 점을 써요.|We write down the advantages together.'
 ].map(row=>row.split('\n').map(line=>line.split('|')));
 const sources=rows.map(row=>row.trim().split('\n').map(line=>line.trim().split('|')));
 if(sources.length!==20||sources.some(row=>row.length!==14||row.some(p=>p.length!==2)))throw Error('Invalid paired reading source');
 const glosses=[
 '아침|morning;창문|window;일어나다|get up;조건|condition',
 '도서관|library;책|book;공책|notebook;문맥|context',
 '비|rain;우산|umbrella;친구|friend;협력|cooperation',
 '공원|park;나무|tree;벤치|bench;서식 환경|habitat',
 '시장|market;채소|vegetables;가격|price;소비량|consumption',
 '요리|cooking;냄비|pot;재료|ingredients;조리 조건|cooking conditions',
 '버스|bus;정류장|bus stop;기다리다|wait;예측|prediction',
 '교실|classroom;이름|name;음악|music;취향|preference',
 '장갑|glove;주머니|pocket;찾다|look for;단서|clue',
 '여행|travel;지도|map;기차표|train ticket;우선순위|priority',
 '휴대전화|mobile phone;대화|conversation;메시지|message;상호작용|interaction',
 '나무|tree;물|water;잎|leaf;관찰 기록|observation record',
 '약속|appointment;시계|clock;미안하다|be sorry;신뢰 회복|restoring trust',
 '도시|city;길|street;안내소|information desk;신뢰도|reliability',
 '공연|performance;연습|practice;역할|role;공정성|fairness',
 '소풍|picnic;교실|classroom;활동|activity;선택지|option',
 '표지판|sign;역|station;안내하다|give directions;선택권|freedom to choose',
 '사진|photograph;서랍|drawer;가족|family;해석|interpretation',
 '화분|plant pot;햇빛|sunlight;식물|plant;통제 조건|controlled condition',
 '선택|choice;방법|method;시간|time;평가 기준|evaluation criterion'
 ].map(row=>row.split(';').map(pair=>pair.split('|')));
 window.HSReadingCurriculum={sources,branches,alternatives,glosses,version:'phase2-20261026'};
})();
