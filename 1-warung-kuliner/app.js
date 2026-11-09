/**
 * Warung Bu Ningsih — Interactive Application Logic
 * Menangani rendering menu interaktif, filter kategori, status buka/tutup dinamis, dan pemesanan WhatsApp.
 */

const MENU = [
  {
    id: "rawon",
    name: "Nasi Rawon Daging Empuk",
    desc: "Potongan daging sapi empuk, kuah kluwak hitam pekat berempah khas Jawa Timur, tauge pendek, telur asin masir, dan sambal terasi segar.",
    price: "28.000",
    cat: "makan",
    tag: "Terlaris",
    tagClass: "tag-hot",
    img: "img/rawon.jpg",
    spicy: true
  },
  {
    id: "ayam-kremes",
    name: "Ayam Goreng Kremes",
    desc: "Ayam ungkep bumbu rempah kuning gurih dengan taburan kremesan bersarang yang sangat renyah, lalapan segar & sambal ulek dadakan.",
    price: "22.000",
    cat: "makan",
    tag: "Favorit",
    tagClass: "tag-fav",
    img: "img/ayam_goreng.jpg",
    spicy: true
  },
  {
    id: "pecel",
    name: "Pecel Komplit Madiun",
    desc: "Sayur rebus segar (bayam, kacang panjang, tauge, kembang turi) disiram bumbu kacang medok kental gurih, disajikan dengan rempeyek renyah.",
    price: "18.000",
    cat: "makan",
    tag: "Sehat",
    tagClass: "tag-fresh",
    img: "img/pecel.jpg",
    spicy: false
  },
  {
    id: "soto",
    name: "Soto Ayam Lamongan",
    desc: "Kuah kuning kaldu ayam kampung gurih segar, suwiran ayam, soun, irisan telur rebus, taburan koya gurih melimpah, dan perasan jeruk nipis.",
    price: "20.000",
    cat: "makan",
    tag: "Hangat",
    tagClass: "tag-warm",
    img: "img/soto.jpg",
    spicy: false
  },
  {
    id: "gorengan",
    name: "Aneka Gorengan Gurih (3 pcs)",
    desc: "Kombinasi tahu isi sayur renyah, tempe mendoan gurih khas Banyumas, dan bakwan sayur garing. Disajikan hangat bersama cabai rawit hijau segar.",
    price: "6.000",
    cat: "camilan",
    tag: "Camilan",
    tagClass: "tag-snack",
    img: "img/gorengan.jpg",
    spicy: false
  },
  {
    id: "es-teh",
    name: "Es Teh Manis Poci Melati",
    desc: "Seduhan teh poci melati wangi khas Jawa, gula tebu asli (bukan pemanis buatan), disajikan dengan es batu kristal melimpah.",
    price: "5.000",
    cat: "minum",
    tag: "Segar",
    tagClass: "tag-fresh",
    img: "img/es_teh.jpg",
    spicy: false
  },
  {
    id: "es-jeruk",
    name: "Es Jeruk Peras Segar",
    desc: "Jeruk manis peras murni tanpa sirup atau pengawet, kombinasi rasa manis dan sedikit asam alami yang sangat melegakan tenggorokan.",
    price: "8.000",
    cat: "minum",
    tag: "Segar",
    tagClass: "tag-fresh",
    img: "img/es_jeruk.jpg",
    spicy: false
  },
  {
    id: "wedang-jahe",
    name: "Wedang Jahe Rempah Hangat",
    desc: "Rebusan jahe emprit bakar geprek berpadu gula aren kelapa, serai wangi, dan cengkeh. Sangat berkhasiat menghangatkan dan menyegarkan badan.",
    price: "7.000",
    cat: "minum",
    tag: "Tradisional",
    tagClass: "tag-warm",
    img: "img/wedang_jahe.jpg",
    spicy: false
  }
];

// Nomor WhatsApp pemilik warung
const WA_PHONE = "6281200000000";

// Render daftar menu
const menuListEl = document.getElementById('menuList');
const menuCountEl = document.getElementById('menuCount');

function renderMenu(filterCategory = 'all') {
  const filtered = MENU.filter(item => filterCategory === 'all' || item.cat === filterCategory);
  
  if (menuCountEl) {
    menuCountEl.textContent = `Menampilkan ${filtered.length} menu`;
  }

  menuListEl.innerHTML = filtered.map(item => {
    const waText = encodeURIComponent(`Halo Bu Ningsih, saya mau pesan ${item.name} (Rp${item.price}). Mohon info ketersediaannya ya.`);
    const waUrl = `https://wa.me/${WA_PHONE}?text=${waText}`;

    return `
      <article class="menu-card" data-category="${item.cat}">
        <div class="menu-img-wrap">
          <img src="${item.img}" alt="${item.name}" loading="lazy" class="menu-card-img">
          ${item.tag ? `<span class="badge-tag ${item.tagClass}">${item.tag}</span>` : ''}
          ${item.spicy ? `<span class="badge-spice" title="Pedas Mantap">🌶️ Pedas</span>` : ''}
        </div>
        <div class="menu-card-content">
          <div class="menu-card-header">
            <h3 class="menu-card-title">${item.name}</h3>
            <span class="menu-card-price">Rp${item.price}</span>
          </div>
          <p class="menu-card-desc">${item.desc}</p>
          <div class="menu-card-action">
            <a href="${waUrl}" target="_blank" rel="noopener" class="btn-order-wa" aria-label="Pesan ${item.name} lewat WhatsApp">
              <span>💬</span> Pesan Menu
            </a>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

// Inisialisasi render pertama
renderMenu('all');

// Tab Filter Handler
const tabButtons = document.querySelectorAll('.tabs .tab-btn');
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    renderMenu(btn.dataset.f);
  });
});

// Jadwal Jam Buka & Status Buka Otomatis
// Indeks hari: 0 = Minggu, 1 = Senin, ..., 6 = Sabtu
const JADWAL = [
  { hari: "Minggu", jam: "08.00 – 16.00", buka: 8, tutup: 16 },
  { hari: "Senin",  jam: "07.00 – 21.00", buka: 7, tutup: 21 },
  { hari: "Selasa", jam: "07.00 – 21.00", buka: 7, tutup: 21 },
  { hari: "Rabu",   jam: "07.00 – 21.00", buka: 7, tutup: 21 },
  { hari: "Kamis",  jam: "07.00 – 21.00", buka: 7, tutup: 21 },
  { hari: "Jumat",  jam: "07.00 – 21.00", buka: 7, tutup: 21 },
  { hari: "Sabtu",  jam: "07.00 – 22.00", buka: 7, tutup: 22 }
];

const now = new Date();
const currentDay = now.getDay();
const currentHour = now.getHours() + (now.getMinutes() / 60);

const jamTableEl = document.getElementById('jamTable');
if (jamTableEl) {
  jamTableEl.innerHTML = JADWAL.map((j, i) => {
    const isToday = (i === currentDay);
    return `
      <tr class="${isToday ? 'row-today' : ''}">
        <td class="col-day">
          ${j.hari} ${isToday ? '<span class="today-chip">Hari Ini</span>' : ''}
        </td>
        <td class="col-hours">${j.jam}</td>
      </tr>
    `;
  }).join('');
}

// Hitung Status Buka / Tutup
const hariIni = JADWAL[currentDay];
const isOpen = currentHour >= hariIni.buka && currentHour < hariIni.tutup;
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');

if (statusBadge && statusText) {
  if (isOpen) {
    statusBadge.className = 'live-status-badge status-open';
    statusText.innerHTML = `<strong>Buka Sekarang</strong> • Tutup jam ${hariIni.tutup}.00 WIB`;
  } else {
    statusBadge.className = 'live-status-badge status-closed';
    const nextBuka = currentHour < hariIni.buka ? hariIni.buka : JADWAL[(currentDay + 1) % 7].buka;
    statusText.innerHTML = `<strong>Sedang Tutup</strong> • Buka kembali pukul ${nextBuka}.00 WIB`;
  }
}
