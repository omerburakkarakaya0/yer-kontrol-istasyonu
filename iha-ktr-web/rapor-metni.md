# 2.5.3 Yer Kontrol İstasyonu

Yer kontrol istasyonu, İHA’nın uçuş verilerinin izlenmesi, görev planlarının yönetilmesi ve operatör müdahalelerinin tek bir arayüz üzerinden gerçekleştirilmesi amacıyla tasarlanmaktadır. Takımımızın mevcut yer kontrol istasyonu altyapısı temel alınarak geliştirilecek sistemin, sabit kanat İHA’nın sekiz çizme ve yük bırakma görevlerine uyarlanması planlanmaktadır. Yazılım mimarisi; kullanıcı arayüzü, telemetri yönetimi, görev planlama ve görüntü aktarımı bileşenlerinden oluşan modüler bir yapı üzerine kurulmaktadır.

İHA ile yer kontrol istasyonu arasındaki çift yönlü haberleşmenin, RFD900x telemetri modülü üzerinden MAVLink protokolü kullanılarak sağlanması planlanmaktadır. Konum, irtifa, hava hızı, yer hızı, batarya ve uçuş modu bilgileri bu haberleşme hattı üzerinden alınacaktır. Bağlantının sürekliliği heartbeat mesajlarıyla izlenecek; uçuş modu değişiklikleri ve görev aktarım işlemleri haberleşme katmanında yürütülecektir. Mevcut altyapıdaki C++ telemetri köprüsünün kullanılmasıyla, telemetri alımı ve ilgili haberleşme işlemlerinin kullanıcı arayüzünden ayrı bir süreçte gerçekleştirilmesi hedeflenmektedir.

Kullanıcı arayüzünün Python ve PyQt5 kullanılarak Qt tabanlı bir masaüstü uygulaması olarak geliştirilmesi planlanmaktadır. Arayüz tasarımı; Uçuş, Görev Planlama ve Görüntüleme olmak üzere üç ana ekrandan oluşmaktadır. Bağlantı ayarları, araç durumu ve görev ilerlemesi ortak yan panelde konumlandırılmıştır. Böylece operatörün ekranlar arasında geçiş yaparken temel uçuş ve bağlantı bilgilerini takip edebilmesi amaçlanmaktadır.

Uçuş ekranında, hava aracının konumu ve izlediği rota harita üzerinde gösterilecek; kamera görüntüsü ile temel uçuş verileri birlikte sunulacaktır. Yapay ufuk göstergesi üzerinden yunuslama ve yatış açıları, ayrı veri alanları üzerinden ise yönelim, irtifa ve GPS koordinatları izlenebilecektir. Batarya seviyesi, hava hızı, yer hızı ve telemetri sinyal durumu, birbirinden ayrılmış göstergelerle operatöre aktarılacaktır. MANUAL, AUTO, GUIDED ve başlangıç konumuna dönüş için RTL modlarına yönelik kontroller aynı ekran üzerinden erişilebilir olacaktır. Bu düzenle, uçuş sırasında ihtiyaç duyulan bilgilerin tek bakışta değerlendirilebilmesi hedeflenmektedir.

Görev Planlama ekranı, sekiz çizme görevinin rota ve görev noktalarının yönetilmesi amacıyla tasarlanmıştır. Görev noktalarının koordinatları, hedef irtifa ve hız değerleri tablo üzerinden düzenlenecek; oluşturulan plan harita üzerinde görüntülenecektir. Aktif görev noktası, tur sayısı ve görev ilerlemesi operatöre sunulacaktır. Görev planının uçuş kontrolcüsüne aktarılması ve araç üzerindeki planın geri okunması desteklenecektir. Harita altyapısında yerel MBTiles verilerinin kullanılmasıyla, önceden indirilen uçuş alanı haritalarının internet bağlantısı bulunmayan koşullarda da görüntülenmesi amaçlanmaktadır.

Görüntüleme ekranında, İHA’dan aktarılacak kamera görüntüsü ile yük bırakma görevine ilişkin hedef ve mekanizma bilgileri birlikte sunulacaktır. Görüntü işleme biriminden alınacak kırmızı ve mavi hedef bölgesi bilgileri; hedef koordinatları, tespit güven değeri ve hedefe mesafe alanlarıyla gösterilecektir. Faydalı yüklerin kilit, servo ve bırakma durumlarının ayrı paneller üzerinden izlenmesi planlanmaktadır. Video hattında RTP/UDP üzerinden alınan görüntünün GStreamer ile çözümlenerek arayüze aktarılması öngörülmektedir. Görev sırasında oluşan durum değişiklikleri ve uyarılar zaman bilgisiyle kayıt alanında gösterilecektir.

Telemetri ve görüntü aktarımı işlemlerinin arayüzü bekletmemesi için asenkron veri akışı ve ayrı iş parçacıkları kullanılacaktır. Arayüz güncellemeleri Qt sinyal-slot mekanizmasıyla gerçekleştirilecek, güncelleme sıklığı sınırlandırılarak gereksiz işlem yükünün azaltılması hedeflenecektir. Bu modüler yapı sayesinde, uçuş takibi ile göreve özgü işlevlerin birlikte yönetilebildiği ve yeni bileşenlerle genişletilebildiği bir yer kontrol istasyonu oluşturulması amaçlanmaktadır.

## Görsel altyazıları

- Şekil 2.5.3.1. Berkut İHA yer kontrol istasyonu uçuş ekranı tasarımı.
- Şekil 2.5.3.2. Sekiz çizme görevine yönelik görev planlama ekranı tasarımı.
- Şekil 2.5.3.3. Hedef görüntüleme ve faydalı yük durumu ekranı tasarımı.

---

Editör notu (rapor metnine dahil değildir): Bu metin, mevcut Python/PyQt5 ve C++ altyapısının İHA görevlerine uyarlanacağı varsayımıyla hazırlanmıştır. HTML arayüz, örnek veriler içeren görsel taslaktır; uçuş testi veya tamamlanmış entegrasyon kanıtı değildir. Eski rapordaki PySide6, MAVSDK, ZeroMQ ve C++ video işleme ifadeleri mevcut kodla birebir örtüşmediğinden aynen aktarılmamıştır. Ekranlardaki sayısal gecikme, kare hızı ve tespit güven değerleri performans sonucu olarak kullanılmamıştır. Şekil numaraları raporun nihai düzenine göre güncellenmelidir.

Referanslar: Berkut İHA raporu, 2.5.3 Yer Kontrol İstasyonu (s. 7–8); Atakum İHA raporu, III. Yer Kontrol İstasyonu (s. 9); mevcut yer kontrol istasyonu kaynak kodu ve iha-ktr-web arayüz taslağı.
