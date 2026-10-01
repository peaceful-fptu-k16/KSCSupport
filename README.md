# KSC Discord Bot

Discord bot gồm hệ thống phát nhạc YouTube/SoundCloud và nền tảng trải nghiệm cộng đồng độc lập.

Tên thương hiệu mặc định trên toàn bộ giao diện là **KSC Gaming**. Có thể cấu hình tập trung bằng `BOT_BRAND_NAME`; mọi tính năng hiện tại và tương lai phải dùng giá trị này thay vì hardcode tên riêng.

## Yêu cầu

- Python 3.11+
- FFmpeg
- Discord bot token
- Bật `Message Content Intent` trong Discord Developer Portal nếu dùng lệnh tiền tố `!`
- Bật `Server Members Intent` để Welcome, Goodbye và hồ sơ thành viên hoạt động

## Cài đặt

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

Trên Linux, dùng `source venv/bin/activate` và `cp .env.example .env`.

Đặt `DISCORD_GUILD_ID` thành ID máy chủ chính để slash command được sync riêng và xuất hiện gần như ngay lập tức. Bot vẫn duy trì bản global command cho các máy chủ khác.

## Lệnh

Mọi lệnh đều dùng được ở dạng `!command` và `/command`.

- `phat [tên hoặc link]`: mở form tìm kiếm hoặc phát trực tiếp YouTube/SoundCloud
- `soundcloud <tên hoặc link>`: tìm và phát từ SoundCloud
- `pause`, `resume`, `skip`, `stop`
- `queue`, `nowplaying`, `volume <0-100>`
- `loop <off|track|queue>`, `shuffle`, `clearqueue`
- `congbang [on|off]`: luân phiên bài hát giữa những người yêu cầu
- `tuphat [on|off]`: tự tìm bài liên quan khi hàng đợi hết
- `yeuthich`: mở thư viện nhạc yêu thích
- `playlist`: mở các playlist đã lưu
- `loibaihat`: xem toàn bộ lời bài đang phát
- `hieuung [preset]`: mở bảng hiệu ứng hoặc chọn Bass Boost, 8D, Nightcore, Vaporwave…
- `equalizer [preset]`: mở equalizer hoặc chọn Cân bằng, Bass, Chill, Vocal, Gaming, Acoustic, EDM
- `lichsu`: xem lịch sử, phát lại hoặc yêu thích bài đã nghe
- `thongke`: xem thời gian nghe, top bài, top nghệ sĩ và thống kê toàn server
- `aidj`: tạo phiên nghe theo mood và lịch sử của bạn
- `radio`: phát liên tục theo một trong 8 mood
- `party`: mở phiên nghe chung, đề xuất bài và vote skip
- `hosonhac`: xem hồ sơ, gu nghe và khung giờ nghe nhạc nhiều nhất
- `wrapped`: xem tổng kết âm nhạc của năm hiện tại
- `help`: hiển thị trợ giúp

### Community

- `hoso`: xem hồ sơ tổng hợp KSC Gaming và huy hiệu nổi bật
- `huyhieu` / `thanhtich`: xem tiến độ; bot tự mở khóa và tự chọn tối đa 5 huy hiệu nổi bật
- `traohuyhieu`: trao huy hiệu đặc biệt không thể đo tự động, dành cho quản trị viên
- `gioithieu`: mở form giới thiệu bản thân và đăng vào kênh introductions
- `sinhnhat [ngày] [tháng] [quyền riêng tư]`: xem hoặc thiết lập sinh nhật
- `lichsinhnhat [tháng]`: xem lịch sinh nhật công khai
- `communitysetup`: kiểm tra các kênh Community, dành cho quản trị viên
- `communitysettings`: mở Community Control Center, dành cho quản trị viên
- `analytics [7|30|90]`: dashboard quản trị theo tab Tổng quan, Thành viên, Chat, Voice, Hoạt động và Retention
- `weekly`: xem Weekly Recap gần nhất với điều hướng 7 trang
- `communitypreview [welcome|birthday|profile|introduction]`: xem thử card đồ họa

Community System tự nhận diện các kênh `welcome`, `introductions`, `celebrations`, `events`, `weekly-recap`, `community-analytics`, `member-log` và `bot-config` kể cả khi tên có emoji. Dữ liệu cộng đồng được lưu riêng tại `data/community.db`.

Welcome Card cung cấp hướng dẫn server, hồ sơ và form giới thiệu. Sinh nhật chỉ lưu ngày/tháng, hỗ trợ ba mức riêng tư; thông báo được đăng một lần mỗi ngày vào `celebrations`. Join/leave, số tin nhắn và thời gian voice được ghi nhận từ khi Community System bắt đầu hoạt động để phục vụ Analytics và Weekly Recap ở các giai đoạn sau.

Birthday Celebration có counter chúc mừng, lời nhắn riêng và bảng lời chúc phân trang. Trong đúng ngày sinh nhật, Profile Card tự chuyển sang theme Pink/Lavender với nhãn Birthday Celebration; không cần cấp role hoặc thao tác thủ công.

Community UI dùng card đồ họa 1200×675 với avatar focus, dark glass, pastel gradient và typography thống nhất. Welcome có animated shimmer/avatar pulse, Birthday có confetti animation; Profile và Introduction dùng PNG sắc nét để tải nhanh. Mỗi GIF được tối ưu dưới giới hạn upload Discord và mọi luồng đều có embed fallback nếu CDN hoặc renderer gặp lỗi.

Achievement System tự mở khóa huy hiệu theo số ngày gắn bó, tin nhắn và thời gian voice. Huy hiệu đặc biệt do quản trị viên trao; chỉ các cột mốc lớn mới được đăng tại `celebrations`. Bot tự chọn tối đa 5 huy hiệu có giá trị nhất để hiển thị trên Profile Card và tự cập nhật khi có thành tích mới.

Community Analytics ghi dữ liệu theo ngày, giờ và kênh, hỗ trợ so sánh 7/30/90 ngày, biểu đồ tăng trưởng, heatmap, peak time, funnel thành viên mới, retention 1/7/30 ngày và Event Analytics. Discord Event được đồng bộ tự động; đăng ký lấy từ Scheduled Event và attendance được xác nhận khi thành viên vào đúng voice channel trong thời gian diễn ra. Bot tự duy trì một dashboard PNG cố định trong `community-analytics` và cập nhật sau 08:00 mỗi ngày; `/analytics` cung cấp bản điều khiển riêng cho quản trị viên.

Community Control Center được bot duy trì như một tin nhắn cố định trong `bot-config`. Quản trị viên có thể bật/tắt Welcome, Goodbye, Birthday, Analytics và Weekly, chọn kênh đích và mức riêng tư Công khai/Tối giản/Chỉ quản trị. Cấu hình được lưu trong SQLite và áp dụng ngay, kể cả sau restart.

Weekly Recap tự tổng hợp tuần Thứ Hai–Chủ Nhật đã hoàn tất gần nhất và đăng một lần vào `weekly-recap` sau 09:00. Recap gồm 7 trang: tổng quan, cộng đồng, hoạt động, thành tựu, highlights, sự kiện và tuần tiếp theo. Nút điều hướng được phục hồi sau khi bot khởi động lại; `period_key` ngăn đăng trùng cùng một tuần.

Ví dụ:

```text
!phat Đường tôi chở em về
!phat https://www.youtube.com/watch?v=...
!phat https://soundcloud.com/btsn-210/dream-love-vol4-trinhanhtuan-x-btsn
!soundcloud Dream Love Vol.4
```

Playlist được giới hạn tối đa 50 bài để tránh một yêu cầu làm nghẽn bot.

Khi dùng `/phat` không kèm nội dung, bot mở form tìm kiếm và trả về tối đa 5 kết quả. Player công khai được tạo một lần rồi cập nhật trực tiếp; các phản hồi từ button và slash command được gửi riêng để giữ kênh chat gọn.

Player sử dụng Discord Components V2 với container có màu nhấn theo nguồn nhạc, media gallery và hai hàng điều khiển tiếng Anh. Bên trong là card PNG 1200×675 được render động với artwork, màu lấy từ album, gradient pastel, waveform và tiến trình phát. Card mặc định làm mới mỗi 30 giây; có thể thay đổi bằng `PLAYER_REFRESH_SECONDS` nhưng giá trị nhỏ nhất là 15 giây.

Yêu thích và playlist được lưu bền vững trong SQLite tại `data/music.db`. Có thể đổi vị trí bằng `MUSIC_DATABASE_PATH`. Lời bài hát được lấy từ LRCLIB, có cache trong phiên chạy và tự chia trang để vừa giới hạn Discord.

Các hiệu ứng thay đổi tốc độ hoặc không gian được xử lý bằng FFmpeg và nối lại tại vị trí hiện tại khi đổi preset. Equalizer được xử lý trực tiếp trên luồng PCM nên đổi EQ không dừng, seek hay tạo lại nguồn phát. Cấu hình được giữ cho các bài tiếp theo và có giới hạn biên độ để giảm clipping.

YouTube được truyền từ `yt-dlp` vào FFmpeg qua pipe để tránh phụ thuộc vào URL CDN tạm thời và lỗi HTTP 403. SoundCloud tiếp tục dùng luồng trực tiếp.

Có thể cấu hình `DISCORD_NOW_PLAYING_WEBHOOK_URL` để đồng bộ một card Now Playing sang kênh khác. Bot cập nhật cùng một webhook message mỗi 30 giây, lưu message ID trong SQLite và hiển thị artwork, tiến trình, volume, hàng đợi cùng người yêu cầu. Khi có tin nhắn mới trong kênh webhook, card được đăng lại ở cuối sau khoảng nghỉ ngắn và bản cũ được xóa.

Có thể cấu hình `DISCORD_SERVER_GUIDE_WEBHOOK_URL` để duy trì một Server Guide cố định gồm giới thiệu KSC Gaming, bản đồ kênh, lệnh Music/Community và nội quy cơ bản. Bot cập nhật cùng một message khi khởi động và tự đăng lại xuống cuối sau khi kênh có hội thoại mới; bản cũ được xóa để không tạo nội dung trùng.

Lịch sử ghi nhận thời điểm bắt đầu, số giây thực tế đã nghe và trạng thái hoàn thành của từng phiên. Thống kê cá nhân chỉ tính các bài do người dùng yêu cầu; thống kê server tổng hợp toàn bộ phiên phát trong server đó.

Hàng đợi công bằng luân phiên theo người yêu cầu nhưng không phá thứ tự riêng của từng người. Tự phát chỉ thêm một bài liên quan khi hàng đợi trống, ưu tiên cùng nguồn và tránh các bài vừa nghe gần đây. Cả hai chế độ có thể bật/tắt trong bảng Hàng đợi hoặc bằng lệnh.

AI DJ tập trung vào V-Pop Official MV/Official Audio với bộ truy vấn nhạc Việt riêng cho từng mood và không yêu cầu API AI trả phí. Kết quả không rõ thời lượng, ngắn dưới 1 phút hoặc dài hơn 12 phút bị loại để tránh phát mix/playlist kéo dài hàng giờ. Radio dùng lịch sử nghe cùng top nghệ sĩ để tạo truy vấn gợi ý rồi tự bật chế độ phát liên tục. Listening Party cho phép thành viên trong cùng voice channel tham gia, đề xuất bài và vote skip theo đa số. Hồ sơ và Wrapped được tính hoàn toàn từ các phiên nghe đã ghi trong SQLite.

## Kiến trúc

```text
bot.py                 Khởi động bot và xử lý lỗi toàn cục
cogs/music.py          Lệnh Discord và nội dung phản hồi
cogs/community.py      Welcome, Birthday và thu thập hoạt động cộng đồng
community/repository.py SQLite repository riêng cho dữ liệu cộng đồng
community/ui.py        Welcome, Introduction, Birthday và Community Profile
community/cards.py     Renderer PNG/GIF cho giao diện Community
music/models.py        Track, queue state và loop state machine
music/extractor.py     Tìm kiếm, metadata và stream YouTube/SoundCloud
music/player.py        Voice lifecycle, đồng bộ queue và chống race condition
music/audio.py         Cấu hình FFmpeg dùng chung
music/effects.py       Preset Effects/EQ và chuỗi filter an toàn
music/errors.py        Lỗi thân thiện có mã ổn định
music/ui/player.py     Persistent player và button điều khiển
music/ui/audio_settings.py Bảng điều khiển Effects và Equalizer
music/ui/history.py    Lịch sử nghe, phát lại và thống kê
music/ui/discovery.py  AI DJ, Radio, Listening Party, Profile và Wrapped
music/ui/search.py     Modal, kết quả tìm kiếm và thao tác với bài hát
music/ui/card.py       Render card pastel, artwork, waveform và progress
music/ui/queue.py      Hàng đợi phân trang, trộn, xóa và lưu playlist
music/ui/library.py    Yêu thích và quản lý playlist cá nhân
music/ui/lyrics_view.py Lời bài hát phân trang
music/repository.py    SQLite repository cho thư viện nhạc
music/lyrics.py        LRCLIB client có throttle và cache
tests/                 Unit test cho state, metadata, library và concurrency
```

Mỗi máy chủ có một `GuildPlayerSession`. Các yêu cầu thêm nhạc được xử lý theo đúng thứ tự nhận, còn `generation` token ngăn luồng âm thanh cũ phát lại sau khi stop hoặc disconnect.

## Kiểm thử

```bash
python -m unittest discover -s tests -v
```
