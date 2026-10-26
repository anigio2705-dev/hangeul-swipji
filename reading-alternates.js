/* Distinct second stories within each theme, with paired sentences and reviewed inferences. */
(() => {
 'use strict';
 const rows=[
 `늦잠을 자서 평소보다 늦게 준비했습니다. 정류장에 도착했을 때 버스는 이미 떠났습니다.|I overslept and got ready later than usual. The bus had already left when I reached the stop.
 다음 버스는 십 분 뒤에 온다고 했습니다. 수업까지는 아직 삼십 분이 남아 있었습니다.|The next bus was due in ten minutes. There were still thirty minutes until class.
 저는 선생님에게 상황을 알렸습니다. 기다리는 동안 오늘 배울 단어를 읽었습니다.|I told my teacher what had happened. While waiting, I read the words for today's lesson.
 다음 버스를 타고 수업 시작 전에 도착했습니다. 다음 날부터는 준비할 물건을 전날 밤에 챙겼습니다.|I took the next bus and arrived before class began. From the next day, I packed what I needed the night before.
 이번에는 늦지 않았지만 같은 여유가 항상 있는 것은 아닙니다. 도착 결과만 보면 준비 과정의 문제를 놓칠 수 있습니다.|I was not late this time, but that margin is not always available. Looking only at the arrival result can hide problems in preparation.
 우연히 시간이 충분했던 것과 준비가 적절했던 것은 구분해야 합니다. 저는 지각 여부와 출발 시각을 따로 기록하기로 했습니다.|Having enough time by chance differs from preparing adequately. I decided to record lateness and departure time separately.
 개선의 기준은 한 번 제시간에 도착했는지가 아니었습니다. 여러 날에 걸쳐 서두르는 일이 줄었는지를 확인하려 했습니다.|The criterion for improvement was not a single on-time arrival. I wanted to see whether rushing decreased across several days.`,
 `도서관에서 독서 모임 안내를 보았습니다. 안내에는 토요일 오후에 모인다고 적혀 있었습니다.|I saw a notice for a reading group in the library. It said the group met on Saturday afternoons.
 저는 참가 신청서를 안내 데스크에 냈습니다. 모임에서 읽을 책은 미리 빌릴 수 있었습니다.|I submitted an application at the information desk. I could borrow the group's book in advance.
 책을 다 읽지 못했지만 모임에 참석했습니다. 진행자는 읽은 부분에 대해서만 이야기해도 된다고 했습니다.|I attended although I had not finished the book. The facilitator said I could discuss just the part I had read.
 다른 사람의 설명을 듣고 남은 부분을 읽고 싶어졌습니다. 다음 모임에서는 읽은 범위를 먼저 밝히기로 했습니다.|Hearing others made me want to read the rest. At the next meeting, I planned to state how far I had read first.
 참여는 완독한 사람에게만 의미가 있는 것은 아닙니다. 다만 읽지 않은 내용을 읽은 것처럼 말해서는 논의가 흐려집니다.|Participation can be meaningful without finishing a book. However, pretending to have read an unread part confuses the discussion.
 경험의 범위를 밝히면 자신의 의견이 어디에 근거하는지 드러납니다. 이는 의견의 크기보다 근거의 범위를 분명히 하는 방법입니다.|Stating the scope of one's experience shows the basis of an opinion. It clarifies the evidence rather than amplifying the opinion.
 모임의 효과를 참석 횟수만으로 평가하기는 어렵습니다. 실제로 읽고 질문하는 방식이 어떻게 달라졌는지도 살펴야 합니다.|Attendance alone cannot adequately measure the group's effect. Changes in reading and questioning also need examination.`,
 `친구가 빌려준 우산을 집으로 가져왔습니다. 다음 날 학교에서 돌려주기로 약속했습니다.|I took home an umbrella my friend had lent me. I promised to return it at school the next day.
 아침에 우산을 말린 뒤 가방 옆에 놓았습니다. 그러나 집을 나설 때 우산을 잊었습니다.|I dried the umbrella and placed it beside my bag in the morning. However, I forgot it when leaving home.
 친구에게 바로 연락해 돌려줄 시간을 다시 정했습니다. 친구는 오후에 우산이 필요하다고 했습니다.|I contacted my friend immediately to arrange a new return time. My friend said the umbrella was needed that afternoon.
 저는 점심시간에 집에 가서 우산을 가져왔습니다. 오후 수업 전에 친구에게 돌려주었습니다.|I went home at lunchtime to fetch it. I returned it before the afternoon class.
 빌린 물건을 깨끗하게 관리하는 것만으로 책임이 끝나지는 않습니다. 상대가 필요한 때에 돌려주는 일도 중요합니다.|Keeping a borrowed item clean does not fulfill every responsibility. Returning it when its owner needs it also matters.
 저는 제 일정만 생각하다가 친구의 사용 계획을 놓쳤습니다. 반환 시점을 함께 확인하니 우선순위를 정할 수 있었습니다.|Thinking only about my schedule made me overlook my friend's plans. Confirming the return time helped me set priorities.
 같은 지연이라도 상대에게 미치는 영향은 다를 수 있습니다. 책임 있는 대응에는 사과와 함께 그 영향을 확인하는 과정이 필요합니다.|The impact of a delay can differ for each person. A responsible response requires checking that impact as well as apologizing.`,
 `아이들이 던진 공이 산책로로 굴러왔습니다. 지나가던 사람이 잠깐 멈추어 공을 피했습니다.|A ball thrown by the children rolled onto the walking path. A passerby paused to avoid it.
 아이들은 공을 가지고 빈 운동장으로 옮겼습니다. 산책로는 계속 걸어 다니는 사람들을 위해 비워 두었습니다.|The children took the ball to an empty playing area. They kept the path clear for people walking through.
 관리인은 놀이 공간의 위치를 안내판에 표시했습니다. 처음 온 사람도 두 공간을 구분할 수 있었습니다.|The caretaker marked the play area's location on a sign. New visitors could also distinguish the two areas.
 아이들은 공놀이를 계속할 수 있었습니다. 산책하는 사람들도 걸음을 자주 멈추지 않아도 되었습니다.|The children could continue playing ball. Walkers no longer had to stop frequently.
 이 경우 해결책은 놀이를 전부 금지하는 것이 아니었습니다. 서로 다른 활동이 겹치는 위치를 조정하는 일이었습니다.|The solution here was not banning all play. It was adjusting where different activities overlapped.
 같은 공간을 쓰는 사람들의 필요를 나누어 보면 대안이 늘어납니다. 한쪽의 요구를 없애야만 다른 쪽이 편해진다고 단정할 필요는 없습니다.|Separating users' needs can reveal more options. One group's needs do not necessarily have to disappear for another group to benefit.
 다만 공간을 나눈 뒤의 실제 이용도 확인해야 합니다. 안내판을 세웠다는 사실만으로 충돌이 해결되었다고 할 수는 없습니다.|Actual use must still be checked after separating areas. Installing a sign alone does not establish that conflicts are resolved.`,
 `시장에서는 감자를 봉지로도 팔고 무게로도 팔았습니다. 봉지 가격은 낮았지만 감자의 양은 표시되어 있지 않았습니다.|The market sold potatoes by the bag and by weight. The bag price was lower, but its quantity was not shown.
 저는 상인에게 봉지의 무게를 물었습니다. 두 상품을 같은 무게의 가격으로 바꾸어 비교했습니다.|I asked the vendor how much the bag weighed. I compared both products using the price for an equal weight.
 필요한 양은 작은 봉지 하나보다 적었습니다. 저는 무게로 파는 가게에서 필요한 만큼만 샀습니다.|I needed less than one small bag. I bought only the amount I needed from the shop selling by weight.
 집에 남아 있던 감자도 함께 요리했습니다. 이번 주에는 감자를 버리지 않고 모두 먹었습니다.|I also cooked the potatoes already at home. This week I ate them all without throwing any away.
 표시 가격만 낮다고 실제 지출이나 낭비가 줄어드는 것은 아닙니다. 단위와 필요한 양을 함께 보아야 비교가 성립합니다.|A lower displayed price does not necessarily reduce spending or waste. A meaningful comparison considers units and the quantity needed.
 단위 가격과 총지출은 서로 다른 질문에 답합니다. 단위 가격이 싸도 많이 사면 총지출은 커질 수 있습니다.|Unit price and total spending answer different questions. A cheap unit price can still produce high spending if much is bought.
 구매를 평가할 때 어느 기준을 사용했는지 밝혀야 합니다. 다른 기준으로 내린 결론을 같은 결론처럼 비교해서는 안 됩니다.|An evaluation of a purchase should state its criterion. Conclusions based on different criteria should not be treated as identical.`,
 `조리법의 재료 목록을 먼저 읽었습니다. 그런데 만드는 순서에 필요한 양파가 목록에는 없었습니다.|I first read the recipe's ingredient list. However, the instructions required an onion absent from the list.
 저는 요리를 멈추고 냉장고를 확인했습니다. 양파가 있어서 필요한 양을 따로 적었습니다.|I stopped cooking and checked the refrigerator. There was an onion, so I noted the amount needed.
 재료를 모두 꺼낸 뒤 처음부터 순서를 확인했습니다. 이번에는 도중에 재료를 찾으러 움직이지 않았습니다.|I took out every ingredient and checked the steps from the start. This time I did not need to search for ingredients midway.
 요리를 마친 뒤 조리법에 빠진 내용을 표시했습니다. 다음에는 수정한 목록으로 준비하기로 했습니다.|After cooking, I marked what the recipe had omitted. I planned to use the corrected list next time.
 조리법의 한 부분이 정확해도 전체 지시가 충분하다고 할 수는 없습니다. 목록과 실제 절차가 서로 맞는지도 확인해야 합니다.|One accurate part does not make a whole recipe sufficient. The list and the actual procedure must also agree.
 초보자에게는 익숙한 사람이 저절로 보충하는 정보도 필요합니다. 설명의 충분함은 작성자가 아니라 사용하는 사람의 관점에서도 살펴야 합니다.|Beginners need information that experienced people supply automatically. Sufficiency must be judged from the user's perspective as well as the writer's.
 이번 수정이 모든 초보자의 어려움을 해결했다고 단정할 수는 없습니다. 다른 사람이 지시만 보고 실행하는 과정도 관찰해야 합니다.|This revision cannot be assumed to resolve every beginner's difficulty. Someone else should also be observed following only the instructions.`,
 `버스가 도착하자 문 앞에 사람들이 모였습니다. 줄이 어디에서 시작하는지 몰라 서로 기다렸습니다.|People gathered by the door when the bus arrived. They waited because they could not tell where the line began.
 한 사람이 줄의 끝을 손으로 가리켰습니다. 뒤에 온 사람들은 그곳에 차례로 섰습니다.|Someone pointed to the end of the line. Later arrivals lined up there in order.
 짐이 큰 승객은 통로를 비운 뒤 천천히 탔습니다. 다른 승객들은 그동안 기다렸습니다.|A passenger with large luggage boarded slowly after the path was cleared. Others waited during that time.
 모두 탄 뒤 문이 닫혔습니다. 운전사는 다음 정류장에서도 내리는 사람을 먼저 기다렸습니다.|The door closed after everyone boarded. At the next stop the driver also waited for people to get off first.
 혼잡은 사람들이 모두 차례를 지키기 싫어서 생긴 것은 아니었습니다. 차례가 시작되는 지점이 보이지 않았던 것도 원인이었습니다.|The crowding was not simply caused by everyone refusing to wait. An unclear starting point was also a cause.
 행동만 비난하면 안내 부족이라는 조건을 놓칠 수 있습니다. 사람의 의도와 행동을 어렵게 만든 환경을 구분할 필요가 있습니다.|Blaming behavior alone can overlook inadequate guidance. Intentions should be distinguished from an environment that makes action difficult.
 안내를 추가한 뒤에도 실제 흐름을 살펴야 합니다. 줄이 생겼다는 사실만으로 모든 승객이 쉽게 탈 수 있었다고 볼 수는 없습니다.|The flow still needs observation after adding guidance. The existence of a line does not show that every passenger could board easily.`,
 `새 친구에게 음악 동아리 신청서를 보여 주었습니다. 신청 마감은 금요일이라고 생각했습니다.|I showed my new friend a music club application. I thought the deadline was Friday.
 안내문을 다시 보니 목요일까지 제출해야 했습니다. 우리는 점심시간에 담당 선생님을 찾아갔습니다.|Reading the notice again showed it had to be submitted by Thursday. We visited the teacher in charge at lunchtime.
 친구는 악기를 잘 다루지 못한다고 말했습니다. 선생님은 노래나 공연 준비로도 참여할 수 있다고 설명했습니다.|My friend said they could not play an instrument well. The teacher explained that singing or preparing performances were also ways to participate.
 친구는 신청서를 내고 준비 모임에 참석했습니다. 저는 다음부터 기억보다 안내문을 먼저 확인하기로 했습니다.|My friend applied and attended the preparation meeting. I decided to check notices before relying on memory next time.
 참여 조건을 확인하지 않았다면 친구는 스스로 기회를 포기했을 수 있습니다. 능숙함이 필요하다는 추측과 실제 신청 조건은 달랐습니다.|Without checking the conditions, my friend might have given up. The assumption that expertise was required differed from the actual entry conditions.
 기회를 안내할 때는 마감과 조건을 함께 정확히 전해야 합니다. 일부 정보만 맞아도 전체 안내가 충분한 것은 아닙니다.|Information about an opportunity should accurately include both deadlines and conditions. Some accurate information does not make the whole explanation sufficient.
 이번 안내가 도움이 된 이유를 친절한 말투만으로 설명할 수는 없습니다. 잘못 기억한 날짜를 확인하고 고친 과정도 중요한 역할을 했습니다.|A kind tone alone does not explain why this guidance helped. Checking and correcting the misremembered date also mattered.`,
 `학교 문 앞에서 제 장갑을 찾았습니다. 그 옆에는 다른 사람이 떨어뜨린 모자도 있었습니다.|I found my glove at the school gate. Beside it was a hat someone else had dropped.
 저는 모자를 교무실에 맡겼습니다. 찾은 장소와 시간을 선생님에게 알려 드렸습니다.|I handed the hat to the teachers' office. I told the teacher where and when I had found it.
 오후에 한 학생이 자기 모자라며 찾아왔습니다. 선생님은 모양과 잃어버린 장소를 확인했습니다.|A student came in the afternoon, saying the hat was theirs. The teacher checked its appearance and where it had been lost.
 모자는 그 학생에게 돌아갔습니다. 저는 물건을 찾은 사람에게도 확인할 책임이 있다는 것을 알았습니다.|The hat was returned to that student. I learned that a finder also has a responsibility to check.
 물건을 발견했다는 사실은 소유자를 안다는 뜻이 아닙니다. 돌려주려는 의도가 좋아도 잘못된 사람에게 줄 가능성은 남습니다.|Finding an item does not mean knowing its owner. Good intentions do not remove the risk of returning it to the wrong person.
 보관 장소와 확인 절차를 정하면 이런 혼동을 줄일 수 있습니다. 이는 도움을 늦추기보다 도움의 대상을 정확하게 만드는 과정입니다.|A storage location and checking procedure can reduce confusion. The process helps identify the right recipient rather than merely delaying help.
 확인에 필요한 정보의 범위도 목적에 맞아야 합니다. 물건의 특징을 확인하는 데 무관한 개인 사정까지 물을 필요는 없습니다.|The information requested should fit the purpose. Checking an item's features does not require unrelated personal details.`,
 `여행 전날 기차 시간이 바뀌었다는 안내를 받았습니다. 새 출발 시각은 원래보다 한 시간 늦었습니다.|The day before the trip, we received notice of a train-time change. The new departure was one hour later.
 가족은 다른 기차로 바꿀지 의논했습니다. 일찍 도착해야 하는 일정은 없어서 변경된 기차를 타기로 했습니다.|My family discussed changing trains. We had no appointment requiring early arrival, so we kept the changed train.
 역에서 기다리기로 했던 시간은 줄였습니다. 대신 집에서 점심을 먹고 출발했습니다.|We reduced the time we had planned to wait at the station. Instead, we ate lunch at home before leaving.
 돌아오는 기차 시간도 다시 확인했습니다. 그 시간에는 변경이 없었습니다.|We also checked the return train time again. It had not changed.
 일정의 일부가 달라졌다고 모든 예약을 바꿀 필요는 없었습니다. 영향을 받는 일정과 영향을 받지 않는 일정을 구분했기 때문입니다.|A change to one part did not require changing every booking. We distinguished affected arrangements from unaffected ones.
 대응의 적절함은 얼마나 많이 변경했는지로 정해지지 않습니다. 바뀐 조건과 여행 목적에 맞게 조정했는지가 중요합니다.|The number of changes does not determine an appropriate response. What matters is adjusting to the new conditions and the trip's purpose.
 이번 판단을 모든 시간 변경에 적용할 수는 없습니다. 도착 시각이 중요한 다른 여행에서는 다른 선택이 필요할 수 있습니다.|This judgment cannot apply to every timetable change. A different trip with a fixed arrival requirement may call for another choice.`,
 `친구와 만나는 동안 전화기를 보지 않기로 했습니다. 만나기 전에 가족에게 연락 가능한 시간을 알려 주었습니다.|I decided not to check my phone while meeting a friend. Beforehand, I told my family when I could be contacted.
 가족은 저녁에 통화하자고 답했습니다. 저는 약속이 끝난 뒤 전화기를 확인했습니다.|My family replied that we could talk in the evening. I checked the phone after the meeting ended.
 낮에 온 메시지에는 바로 답하지 않았습니다. 하지만 정해 둔 저녁 시간에는 전화를 걸었습니다.|I did not reply immediately to daytime messages. However, I called at the agreed evening time.
 친구와의 대화도 가족과의 연락도 이어졌습니다. 다음 약속에도 연락 시간을 미리 조정하기로 했습니다.|Both the conversation with my friend and contact with my family continued. I planned to coordinate contact times before the next meeting too.
 연락을 줄이는 선택은 관계를 끊는 선택과 다를 수 있습니다. 상대가 기다릴 시간을 알 수 있게 하는 것이 두 선택의 차이를 분명하게 했습니다.|Reducing contact can differ from cutting a relationship off. Letting others know when to expect contact helped distinguish the choices.
 제 생활 방식이 편하다는 이유만으로 상대의 기다림을 무시할 수는 없습니다. 개인의 집중과 관계의 예측 가능성을 함께 고려해야 합니다.|My convenience does not justify ignoring another person's waiting. Personal concentration and predictability in a relationship both matter.
 다만 모든 관계가 같은 연락 간격을 필요로 하지는 않습니다. 적절한 시간은 상대의 필요와 상황을 확인하며 정해야 합니다.|Not every relationship requires the same contact interval. Appropriate timing should be agreed by checking needs and circumstances.`,
 `학생 두 명이 같은 날 나무에 물을 주었습니다. 서로 누가 담당인지 다르게 알고 있었습니다.|Two students watered the tree on the same day. They had different understandings of who was responsible.
 담당표에는 이름만 있고 날짜가 없었습니다. 우리는 날짜와 확인 칸을 새로 넣었습니다.|The duty chart had names but no dates. We added dates and confirmation boxes.
 담당 학생은 물을 주기 전에 흙의 상태를 확인했습니다. 일을 마친 뒤 표에 기록했습니다.|The student in charge checked the soil before watering. After finishing, the student recorded it on the chart.
 다음 주에는 같은 일을 중복하는 날이 줄었습니다. 빠진 기록이 있으면 서로 확인했습니다.|The next week, fewer days had duplicated work. We checked with each other when a record was missing.
 이름이 적혀 있다는 사실만으로 역할이 명확한 것은 아닙니다. 언제 무엇을 해야 하는지도 전달되어야 합니다.|Listing a name does not by itself make a role clear. When and what to do must also be communicated.
 책임을 개인에게만 돌리면 불완전한 담당표를 그대로 둘 수 있습니다. 반복되는 실수에는 정보를 전달하는 방식의 문제도 있을 수 있습니다.|Blaming only individuals can leave an incomplete chart unchanged. Repeated mistakes may also reflect how information is communicated.
 새 표가 생겼다고 관리가 완성되었다고 볼 수는 없습니다. 기록이 실제 행동과 맞는지 계속 살펴야 합니다.|A new chart does not establish that care is complete. Records must continue to be checked against actual actions.`,
 `달력을 보니 같은 시간에 약속이 두 개 있었습니다. 하나는 친구와의 만남이고 다른 하나는 모임이었습니다.|My calendar showed two appointments at the same time. One was a meeting with a friend and the other a group meeting.
 저는 친구에게 가능한 다른 시간을 물었습니다. 친구는 다음 날 오전이 괜찮다고 했습니다.|I asked my friend about other possible times. My friend said the next morning would work.
 모임에는 원래 시간에 참석했습니다. 친구와의 약속은 다음 날로 옮겼습니다.|I attended the group meeting at its original time. I moved the appointment with my friend to the next day.
 바뀐 약속은 달력에 바로 고쳐 적었습니다. 친구에게도 변경된 시간을 다시 확인했습니다.|I immediately corrected the changed appointment in my calendar. I also reconfirmed the new time with my friend.
 혼자 달력을 고치는 것만으로 약속이 바뀌지는 않습니다. 함께 만나기로 한 사람의 동의도 필요합니다.|Changing a calendar alone does not change a shared appointment. The other person's agreement is also needed.
 이번 조정은 어느 약속이 더 가치 있는지 평가한 결과가 아니었습니다. 변경할 수 있는 조건이 서로 달랐기 때문입니다.|This adjustment did not rank the appointments' value. Their conditions for rescheduling differed.
 관계의 중요도와 일정 변경의 가능성을 혼동해서는 안 됩니다. 적절한 설명은 시간 조정이 불필요한 오해로 이어지는 것을 줄입니다.|A relationship's importance should not be confused with scheduling flexibility. A suitable explanation reduces unnecessary misunderstandings.`,
 `지도에는 박물관까지 가장 짧은 길이 표시되었습니다. 하지만 그 길에는 긴 계단이 있었습니다.|The map showed the shortest route to the museum. However, that route included a long staircase.
 무거운 여행 가방을 들고 있어서 다른 길을 물었습니다. 안내소 직원은 계단이 없는 길을 알려 주었습니다.|I had a heavy travel bag, so I asked about another route. The information worker explained a route without stairs.
 돌아가는 거리는 조금 늘어났습니다. 대신 가방을 계속 들고 계단을 오르지 않아도 되었습니다.|The distance became a little longer. In exchange, I did not have to carry the bag up the stairs.
 저는 두 길의 차이를 지도에 적었습니다. 다음에는 거리뿐 아니라 이동 조건도 확인하기로 했습니다.|I noted the difference between the two routes on the map. Next time I planned to check travel conditions as well as distance.
 가장 짧은 길이 모든 사람에게 가장 편한 길은 아닙니다. 이동하는 사람의 조건에 따라 평가 기준이 달라집니다.|The shortest route is not the easiest for everyone. Evaluation criteria vary with the traveler's circumstances.
 하나의 순위만 제시하면 그 순위의 기준이 보이지 않을 수 있습니다. 거리가 짧다는 정보와 계단이 없다는 정보는 서로 다른 필요를 충족합니다.|A single ranking can hide its criteria. Information about distance and about the absence of stairs serves different needs.
 안내의 정확성은 거리 계산만으로 결정되지 않습니다. 이용자가 판단하는 데 필요한 조건이 함께 제공되는지도 중요합니다.|Accurate guidance is not determined by distance calculations alone. It also matters whether relevant conditions are provided.`,
 `공연 연습 중에 스피커가 갑자기 멈췄습니다. 노래하던 친구들은 다음 순서를 몰라 기다렸습니다.|The speaker suddenly stopped during rehearsal. The singers waited because they did not know what to do next.
 우리는 음악이 멈췄을 때 사용할 손 신호를 정했습니다. 안내 문구도 종이에 적어 두었습니다.|We agreed on a hand signal for when music stopped. We also wrote guidance on paper.
 다시 연습하면서 일부러 음악을 끊어 보았습니다. 이번에는 신호를 보고 다음 순서로 넘어갔습니다.|In the next rehearsal, we deliberately stopped the music. This time we followed the signal and moved to the next step.
 실제 공연에서는 스피커가 정상 작동했습니다. 그래도 대처 방법을 정해 두니 덜 불안했습니다.|The speaker worked during the actual performance. Having a response prepared still made us less anxious.
 대비책의 가치는 실제 사고가 났을 때만 생기는 것은 아닙니다. 역할과 신호를 함께 확인하는 과정도 준비에 도움이 됩니다.|A contingency plan can be valuable even when no failure occurs. Checking roles and signals together also helps preparation.
 그러나 신호를 정했다는 말과 신호에 따라 움직일 수 있다는 것은 다릅니다. 실제로 음악을 끊은 연습이 그 차이를 확인하게 했습니다.|Agreeing on a signal differs from being able to act on it. The rehearsal with interrupted music tested that distinction.
 사고가 없었다는 결과만으로 대비책의 효과를 입증할 수는 없습니다. 예상 상황에서 실제로 작동하는지를 별도로 확인해야 합니다.|The absence of an accident does not prove a plan's effectiveness. Its operation in the expected situation must be checked separately.`,
 `실내 활동을 고를 때 여섯 명은 게임을 원했습니다. 네 명은 조용히 책을 읽고 싶어 했습니다.|When choosing indoor activities, six students wanted games. Four wanted to read quietly.
 처음에는 표가 많은 게임만 하려고 했습니다. 그러나 교실을 두 구역으로 나눌 수 있다는 의견이 나왔습니다.|At first we planned to offer only the game with more votes. Then someone suggested dividing the classroom into two areas.
 한쪽에서는 작은 목소리로 게임을 했습니다. 다른 쪽에서는 책을 읽었습니다.|One side played games in quiet voices. The other side read books.
 끝난 뒤 두 구역의 소리가 서로 방해되었는지 물었습니다. 다음에는 자리를 더 멀리 나누기로 했습니다.|Afterward we asked whether sound from either area had disturbed the other. Next time we planned to separate the areas further.
 여섯 표가 많다는 사실은 네 명의 필요가 없다는 뜻이 아닙니다. 하나만 골라야 한다는 전제를 바꾸자 다른 대안이 보였습니다.|Six being more votes does not erase four students' needs. Changing the assumption that only one option was allowed revealed another solution.
 다수의 선택과 전체의 만족은 같은 수치가 아닙니다. 의사결정 방식에 따라 드러나는 정보도 달라집니다.|The majority's choice and everyone's satisfaction are different measures. Decision methods reveal different information.
 두 활동을 제공했다는 사실만으로 배려가 충분했다고 결론 내릴 수는 없습니다. 서로의 활동을 실제로 방해하지 않았는지까지 확인해야 합니다.|Offering both activities alone does not establish sufficient consideration. Whether they actually interfered with each other must also be checked.`,
 `지도에는 역의 입구가 길 건너편에 있다고 나왔습니다. 현장에는 공사 중이라는 안내가 있었습니다.|The map placed the station entrance across the street. A notice on site said construction was in progress.
 저는 예전 지도만 보고 들어가라고 하지 않았습니다. 안내문에 표시된 임시 입구를 함께 확인했습니다.|I did not tell the traveler to enter based only on the old map. We checked the temporary entrance shown on the notice together.
 임시 입구는 다음 골목에 있었습니다. 안내 화살표를 따라가니 실제 출입구가 보였습니다.|The temporary entrance was in the next alley. Following the arrows brought an actual entrance into view.
 여행자는 역 안으로 들어갔습니다. 저는 처음 본 지도와 현장 안내가 다를 수 있음을 기억했습니다.|The traveler entered the station. I remembered that an initial map can differ from on-site information.
 두 자료가 다르다고 아무 자료나 선택할 수는 없습니다. 갱신 시점과 실제 현장 상황을 함께 대조해야 합니다.|Conflicting sources do not justify choosing arbitrarily. Their update times and the actual situation must be compared.
 이 사례에서는 임시 안내가 현재의 출입 조건을 설명했습니다. 지도가 유용하다는 일반적인 평가와 이 지도 정보의 최신성은 다른 문제입니다.|Here the temporary notice explained current access. The general usefulness of maps and this map's currency are separate issues.
 안내를 마친 뒤에도 확인하지 않은 다른 출구까지 정확하다고 확대해서 말하지 않았습니다. 확인한 범위에 맞게 설명하는 태도가 필요하기 때문입니다.|I did not extend the claim of accuracy to other unchecked exits. An explanation should match what was actually verified.`,
 `가족사진의 색을 밝게 고친 파일을 받았습니다. 원래 사진에는 없던 밝은 색이 더해져 있었습니다.|I received a family photograph edited to brighten its colors. Bright colors absent from the original had been added.
 저는 수정한 파일과 원본을 나누어 보관했습니다. 가족에게 보여 줄 때 색을 바꾼 사진이라고 말했습니다.|I stored the edited file separately from the original. When showing it to my family, I said its colors had been changed.
 한 사람은 옛날 건물도 그 색이었는지 물었습니다. 우리는 원본에서 확인할 수 있는 부분을 함께 살폈습니다.|Someone asked whether the old building had really been that color. We examined what could be established from the original.
 원래 색은 사진만으로 확실히 알기 어려웠습니다. 그래서 수정한 색을 당시의 사실로 기록하지 않았습니다.|The original color was difficult to establish from the photograph alone. We therefore did not record the edited color as a historical fact.
 보기 편하게 만든 자료와 과거를 증명하는 자료는 역할이 다를 수 있습니다. 편집 과정이 드러나야 보는 사람이 그 차이를 판단할 수 있습니다.|A more visually pleasing image and historical evidence can serve different roles. Disclosing the editing lets viewers assess that distinction.
 원본을 보존하면 수정 과정과 결과를 비교할 수 있습니다. 그렇다고 원본 사진 하나가 과거의 모든 모습을 담는 것은 아닙니다.|Preserving the original allows comparison with the edit. But one original photograph does not show every aspect of the past.
 자료를 해석할 때는 원본의 한계와 편집으로 생긴 변화를 모두 고려해야 합니다. 어느 쪽도 설명하지 않으면 사실과 추정이 섞일 수 있습니다.|Interpretation should consider both the original's limits and changes from editing. Omitting either can mix facts with estimates.`,
 `화분의 키를 재서 십이라고 적었습니다. 다음 날 다른 학생은 백이라고 기록했습니다.|I measured the potted plant's height and wrote ten. The next day another student recorded one hundred.
 처음에는 하루 만에 많이 자란 줄 알았습니다. 하지만 첫 기록은 센티미터이고 둘째 기록은 밀리미터였습니다.|At first we thought it had grown greatly in a day. However, the first record used centimeters and the second millimeters.
 십 센티미터는 백 밀리미터였습니다. 같은 단위로 바꾸니 두 기록의 길이가 같았습니다.|Ten centimeters equaled one hundred millimeters. Converting to the same unit showed equal lengths.
 우리는 기록표에 단위를 쓰는 칸을 넣었습니다. 이후에는 길이와 단위를 함께 적었습니다.|We added a space for units to the record sheet. After that we recorded both the length and its unit.
 숫자가 커졌다는 사실만으로 실제 대상이 커졌다고 할 수는 없습니다. 측정 단위가 같다는 조건이 먼저 확인되어야 합니다.|A larger number alone does not show a larger object. Equal measurement units must first be established.
 단위를 맞춘 것은 불편한 결과를 없애기 위해서가 아니었습니다. 서로 다른 기록을 비교할 수 있는 형태로 바꾸기 위해서였습니다.|Matching units was not intended to remove an inconvenient result. It made the records comparable.
 비교 가능한 자료를 만드는 과정도 조사 결과의 일부입니다. 숫자만 제시하면 독자는 그 전제를 확인하지 못할 수 있습니다.|Making data comparable is also part of an investigation. Presenting only numbers can hide those assumptions from readers.`,
 `친구는 일자리 두 곳 중 하나를 고르고 있었습니다. 한 곳은 시급이 높고 다른 곳은 집에서 가까웠습니다.|My friend was choosing between two jobs. One offered higher hourly pay and the other was nearer home.
 우리는 근무 시간과 이동 시간을 함께 적었습니다. 가까운 곳은 왕복 이동 시간이 한 시간 짧았습니다.|We listed working hours and travel time together. The nearer job had a round trip one hour shorter.
 친구는 저녁에 수업을 듣고 싶어 했습니다. 그래서 시급만으로 두 일을 비교하지 않았습니다.|My friend wanted to take evening classes. We therefore did not compare the jobs by hourly pay alone.
 친구는 수업 시간과 맞는 가까운 일자리를 골랐습니다. 저는 친구가 사용한 기준을 기록했습니다.|My friend chose the nearer job that fit the class schedule. I recorded the criteria my friend used.
 다른 사람이 높은 시급을 고르더라도 반드시 잘못된 선택은 아닙니다. 필요한 소득과 사용할 수 있는 시간이 서로 다를 수 있기 때문입니다.|Someone choosing higher pay is not necessarily wrong. Income needs and available time can differ.
 선택을 비교할 때는 같은 목표를 가정하고 있는지 살펴야 합니다. 목표가 다른 선택을 결과 하나로만 순위 매기기는 어렵습니다.|Comparisons should check whether the same goal is assumed. Choices with different goals are hard to rank by a single outcome.
 이번 선택이 장기적으로도 적절했는지는 이후에 확인해야 합니다. 결정 당시의 이유가 분명하다는 것과 결과가 보장된다는 것은 다릅니다.|The long-term suitability of this choice needs later review. Clear reasons at the time do not guarantee an outcome.`
 ];
 const split=text=>text.match(/[^.!?]+[.!?]/g).map(s=>s.trim());
 const passages=rows.map(row=>row.trim().split('\n').flatMap(line=>{const [ko,en]=line.trim().split('|'),a=split(ko),b=split(en);if(a.length!==2||b.length!==2)throw Error('Alternate sentence alignment');return a.map((s,i)=>[s,b[i]])}));
 if(passages.length!==20||passages.some(p=>p.length!==14))throw Error('Alternate reading count');
 // Each inference is tied to explicit sentences; the distractors reverse or overstate them.
 const inferenceRows={
 0:["버스를 놓친 뒤에도 수업 전에 도착할 수 있었던 이유는?","Why could the narrator still arrive before class?",[2,3,6],[["수업까지 남은 시간이 다음 버스 대기 시간보다 길었습니다.","There was more time before class than the wait for the next bus."],["수업 시작 시각을 늦췄기 때문입니다.","The class start time was postponed."],["이미 떠난 버스가 돌아왔기 때문입니다.","The departed bus came back."],["선생님이 집으로 왔기 때문입니다.","The teacher came to the narrator's home."]]],
 4:["가격을 비교할 때 가장 주의해야 할 것은?","What most needs attention when comparing the prices?",[0,1,2,3],[["가격이 어떤 수량을 기준으로 하는지 확인해야 합니다.","Check what quantity each price covers."],["포장 가격이 낮으면 같은 양도 반드시 더 쌉니다.","A lower package price guarantees a lower price for equal quantities."],["남을 감자는 비용과 관계가 없습니다.","Unused potatoes have nothing to do with cost."],["봉지가 크면 필요한 양을 계산할 필요가 없습니다.","A larger bag removes the need to estimate the amount needed."]]],
 6:["줄을 안내할 때 먼저 확인할 문제는?","What should be checked first when organizing the queue?",[0,1,2,3],[["사람들이 줄의 시작을 같은 곳으로 이해하는지입니다.","Whether people understand the queue to start in the same place."],["나중에 온 사람은 모두 새치기했다는 사실입니다.","That everyone who arrived later deliberately cut in."],["버스가 이미 떠났다는 사실입니다.","That the bus has already departed."],["기다리는 사람이 전혀 없다는 사실입니다.","That nobody is waiting."]]],
 7:["신청에 관한 판단을 바꾼 근거는?","What evidence changed the decision about applying?",[0,1,2,3],[["기억과 달리 안내문의 마감일은 목요일이었습니다.","Unlike the remembered date, the notice gave Thursday as the deadline."],["금요일까지 기다려도 된다는 새 안내가 왔습니다.","A new notice said waiting until Friday was allowed."],["음악을 잘하는 사람만 신청할 수 있었습니다.","Only skilled musicians could apply."],["신청서가 필요 없다고 확인했습니다.","It was confirmed that no application was needed."]]],
 9:["더 늦은 기차를 선택해도 된다고 판단한 이유는?","Why was a later train acceptable?",[0,1,2,3],[["일찍 도착해야 하는 정해진 약속이 없었습니다.","There was no fixed appointment requiring an early arrival."],["기차표를 사지 않아도 되었기 때문입니다.","No ticket was needed."],["첫 기차의 출발 시각이 더 늦었기 때문입니다.","The first train departed later."],["모든 일정이 취소되었기 때문입니다.","Every activity had been cancelled."]]],
 11:["표에 날짜를 쓰고 물을 준 뒤 표시하는 이유는?","Why add dates and mark the chart after watering?",[0,1,2,3,4,5],[["누가 언제 물을 주었는지 구분하기 위해서입니다.","To distinguish who watered the tree and when."],["물을 더 자주 주는 사람이 이기게 하기 위해서입니다.","To reward whoever waters most often."],["나무를 돌보는 일을 중단하기 위해서입니다.","To stop caring for the tree."],["날짜가 있으면 물을 줄 필요가 없어지기 때문입니다.","Dates remove the need to water it."]]],
 13:["가장 짧은 길을 고르지 않은 이유는?","Why was the shortest route not chosen?",[0,1,2,3,4,5],[["무거운 가방을 들고 계단을 지나야 했기 때문입니다.","It required carrying a heavy bag up or down stairs."],["긴 길이 언제나 더 빠르기 때문입니다.","A longer route is always faster."],["박물관이 문을 닫았기 때문입니다.","The museum had closed."],["지도에 짧은 길이 표시되지 않았기 때문입니다.","The short route was absent from the map."]]],
 15:["투표 결과만으로 모두의 선호가 같다고 말할 수 없는 이유는?","Why does the vote not show that everyone has the same preference?",[0,1,2,3],[["책을 읽고 싶어 하는 네 명도 있었기 때문입니다.","Four students also wanted to read."],["열 명 모두 공놀이를 원했기 때문입니다.","All ten wanted to play ball."],["아무도 투표하지 않았기 때문입니다.","Nobody voted."],["투표에서 활동을 정할 수 없다는 규칙이 있기 때문입니다.","A rule forbids choosing activities through a vote."]]],
 17:["수정한 색을 당시 사실로 기록하지 않은 이유는?","Why were the edited colors not recorded as historical fact?",[0,1,2,3,4,5,6,7],[["보기 좋게 바꾼 색이 원래 색이라는 증거는 아니기 때문입니다.","Visually improved colors are not evidence of the original colors."],["수정한 파일은 모두 원본과 완전히 같기 때문입니다.","Edited files are always identical to originals."],["가족이 사진을 본 적이 없기 때문입니다.","The family had never seen the photograph."],["원본이 전혀 남아 있지 않았기 때문입니다.","No original remained."]]],
 18:["두 키 기록만 보고 식물이 자랐다고 판단할 수 없는 이유는?","Why do the two height records not establish growth?",[0,1,2,3,4,5],[["10센티미터와 100밀리미터는 같은 길이이기 때문입니다.","Ten centimeters and one hundred millimeters are the same length."],["밀리미터는 길이를 나타내지 않기 때문입니다.","Millimeters do not measure length."],["100밀리미터가 10센티미터보다 열 배 길기 때문입니다.","One hundred millimeters is ten times ten centimeters."],["식물에는 길이를 측정할 수 없기 때문입니다.","Plant heights cannot be measured."]]]
 };
 const glosses=[["늦잠","oversleeping"],["독서 모임","reading group"],["빌려주다","to lend"],["통로","passage; walkway"],["무게","weight"],["양파","onion"],["줄","queue; line"],["마감일","deadline"],["분실물","lost property"],["출발 시각","departure time"],["연락","contact"],["담당","person in charge"],["겹치다","to overlap"],["계단","stairs"],["손짓","hand signal"],["구역","section; area"],["임시 입구","temporary entrance"],["원본","original"],["밀리미터","millimeter"],["통근 시간","commuting time"]];
 window.HSReadingAlternates={passages,inferenceRows,glosses};
})();
