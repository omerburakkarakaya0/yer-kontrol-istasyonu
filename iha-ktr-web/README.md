# BERKUT İHA – KTR görsel arayüzü

Bu klasör, rapor için ekran görüntüsü üretmeye yönelik bağımsız HTML/CSS/JavaScript taslağıdır. Gerçek İHA bağlantısı, telemetri alımı, video aktarımı veya komut gönderimi yapmaz. Sayılardaki başarı, gecikme ve hedef tespit değerleri ölçüm sonucu değildir; örnek gösterimdir.

## Açılış

`dist/index.html` dosyasına çift tıkla. İnternet, paket kurulumu veya sunucu gerektirmez. Dosyaları aynı klasör düzeninde tut.

- **1:** Uçuş ekranı
- **2:** Görev planlama ekranı
- **3:** Görüntüleme ve faydalı yük ekranı
- **F** veya **Tam ekran:** ekranı büyütür. Çıkış: Escape.
- Sekmeler ve uçuş modu düğmeleri görsel durumu değiştirir. Diğer komut düğmeleri yalnızca önizleme bildirimi gösterir.

Geniş masaüstü ekranı için 1800 × 1000 oranında tasarlanmıştır ve pencereye sığar. Rapor için hazır PNG dosyaları `screenshots` klasöründedir. Fotoğraf çekerken sayfa üzerinde örnek veriler kullanıldığı bilgisi korunur.

## Görseller ve referanslar

- Renkler ve panel düzeni mevcut BLACK BOX SİHA masaüstü arayüzünden uyarlanmıştır.
- Uçuş ekranında HUD, hedef bilgileri, telemetri ve mod/görev kontrol panelleri bulunur. Araç modeli görünümden kaldırılmıştır.
- Harita, mevcut projedeki Bing kaynaklı yerel MBTiles dosyasından alınmıştır. Çizilen rota ve gösterilen konumlar görsel taslaktır; coğrafi uçuş planı değildir.
- Kamera alanı, mevcut projedeki `ktr_gorsel.jpg` örnek görüntüsünü kullanır. Görüntüleme ekranındaki tespit kutusu işlevsel algoritma çıktısı değildir.
- Berkut raporunda yer kontrol istasyonu: 2.5.3, sayfa 7–8. Atakum raporunda: III. Yer Kontrol İstasyonu, sayfa 9. Atakum'un metni ve görseli kopyalanmamıştır.

Rapor metni sonraki aşamada kesinleşmiş mimari ve uygulanması planlanan özellikler üzerinden yazılmalıdır. Bu görseller, uygulamanın tamamlandığı veya testlerin gerçekleştirildiği anlamına gelmez.

## Düzenleme

`dist/styles.css`: görünüm; `dist/app.js`: ekranlar ve örnek veriler; `dist/index.html`: başlık ve ortak kenar paneli. Mevcut Python/C++ yer kontrol istasyonu kodu değiştirilmemiştir.
