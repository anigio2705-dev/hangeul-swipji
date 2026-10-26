'use strict';
const target=new URL(location.pathname.includes('/phase3/')?'../index.html':'./index.html',location.href);target.search=location.search;target.hash='teaching-platform';location.replace(target.href);
