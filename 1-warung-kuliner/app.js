const MENU=[
["Nasi Rawon","Daging empuk, kuah kluwak, telur asin","28.000","makan","Favorit"],
["Ayam Goreng Kremes","Dengan sambal terasi & lalapan","22.000","makan"],
["Pecel Komplit","Sayur rebus, bumbu kacang, rempeyek","18.000","makan"],
["Soto Ayam","Bening, koya gurih","20.000","makan"],
["Gorengan (3 pcs)","Tahu isi, tempe mendoan, bakwan","6.000","makan"],
["Es Teh Manis","Teh poci wangi","5.000","minum"],
["Es Jeruk Peras","Jeruk asli, tanpa sirup","8.000","minum"],
["Wedang Jahe","Hangat, pas musim hujan","7.000","minum"]];
const ul=document.getElementById('menuList');
function render(f){ul.innerHTML=MENU.filter(m=>f=='all'||m[3]==f).map(m=>
`<li><div><span class="n">${m[0]}${m[4]?`<span class="tag">${m[4]}</span>`:''}</span><span class="d">${m[1]}</span></div><span class="dots"></span><span class="p">Rp${m[2]}</span></li>`).join('')}
render('all');
document.querySelector('.tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;
document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x==b));render(b.dataset.f)};
// jam buka (0 = Minggu)
const H=["Minggu|08.00–15.00","Senin|07.00–21.00","Selasa|07.00–21.00","Rabu|07.00–21.00","Kamis|07.00–21.00","Jumat|07.00–21.00","Sabtu|07.00–22.00"];
const now=new Date(),d=now.getDay();
document.getElementById('jam').innerHTML=H.map((h,i)=>{const[a,b]=h.split('|');return`<tr class="${i==d?'today':''}"><td>${a}</td><td>${b}</td></tr>`}).join('');
const[o,c]=H[d].split('|')[1].split('–').map(t=>+t.split('.')[0]);
const open=now.getHours()>=o&&now.getHours()<c;
const s=document.getElementById('status');s.textContent=open?'🟢 Buka sekarang':'🔴 Tutup sekarang';
